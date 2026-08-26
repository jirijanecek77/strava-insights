import logging
from app.garmin_client import (
    GarminActivityStreamNotFoundError,
    GarminApiClient,
)
from app.models import Activity, ActivityStream
from app.repositories import (
    ActivityRepository,
    ActivityStreamRepository,
    GarminCredentialRepository,
    SyncCheckpointRepository,
    SyncJobRepository,
)
from app.security import TokenCipher
from app.services.activity_summary import (
    average_speed_mps,
    distance_km,
    format_moving_time,
    format_pace,
    pace_seconds_per_km,
    speed_kph,
    summary_metric_display,
)
from app.services.cache_invalidator import UserCacheInvalidator
from app.services.local_route_matcher import ROUTE_MODEL_VERSION
from app.services.read_model_builder import ReadModelBuilder
from app.services.route_index_builder import RouteIndexBuilder, RouteIndexStats
from app.services.stream_sanitizer import sanitize_stream_payload
from datetime import UTC, datetime
from decimal import Decimal
from sqlalchemy.orm import Session

SUPPORTED_SPORTS = {"Run", "Ride", "EBikeRide"}
ACTIVITY_CHECKPOINT_TYPE = "activities"
ANALYTICS_CHECKPOINT_TYPE = "analytics_model"
ANALYTICS_MODEL_VERSION = "2"
ROUTE_CHECKPOINT_TYPE = "route_model"
logger = logging.getLogger(__name__)


class BaseImportService:
    def __init__(
        self,
        session: Session,
        *,
        garmin_client: GarminApiClient | None = None,
        token_cipher: TokenCipher | None = None,
    ) -> None:
        self.session = session
        self.garmin_client = garmin_client or GarminApiClient()
        self.token_cipher = token_cipher or TokenCipher()
        self.garmin_credentials = GarminCredentialRepository(session)
        self.sync_jobs = SyncJobRepository(session)
        self.activities = ActivityRepository(session)
        self.activity_streams = ActivityStreamRepository(session)
        self.checkpoints = SyncCheckpointRepository(session)
        self.cache_invalidator = UserCacheInvalidator()
        self.read_model_builder = ReadModelBuilder(session)
        self.route_index_builder = RouteIndexBuilder(session)

    def run(self, *, sync_job_id: int, user_id: int) -> int:
        raise NotImplementedError

    def _run(self, *, sync_job_id: int, user_id: int, after: datetime | None) -> int:
        sync_job = self.sync_jobs.get(sync_job_id, user_id)
        if sync_job is None:
            raise ValueError("Sync job not found.")
        logger.info(
            "Starting import service run.",
            extra={
                "sync_job.id": sync_job_id,
                "user.id": user_id,
                "after": None if after is None else after.isoformat(),
            },
        )

        token_json = self._get_garmin_credentials(user_id)
        activities_payload = [
            activity
            for activity in self.garmin_client.get_activities(
                token_json, after=after
            )
            if activity.get("type") in SUPPORTED_SPORTS
        ]
        existing_source_activity_ids = (
            self.activities.list_existing_source_activity_ids_for_user(
                user_id,
                [
                    activity["id"]
                    for activity in activities_payload
                    if activity.get("id") is not None
                ],
            )
        )
        activities_payload = [
            activity
            for activity in activities_payload
            if activity.get("id") not in existing_source_activity_ids
               or self._existing_activity_needs_stream_backfill(
                user_id=user_id, source_activity_id=activity["id"]
            )
        ]
        logger.info(
            "Fetched Garmin activities for import.",
            extra={
                "sync_job.id": sync_job_id,
                "user.id": user_id,
                "fetched_count": len(activities_payload),
                "existing_count": len(existing_source_activity_ids),
            },
        )
        self.sync_jobs.update_running(sync_job, progress_total=len(activities_payload))
        self.session.commit()

        imported_count = 0
        latest_checkpoint_value = self._get_existing_checkpoint_value(user_id)

        for index, activity_payload in enumerate(activities_payload, start=1):
            activity = self._upsert_activity(user_id=user_id, payload=activity_payload)
            try:
                stream_payload = self.garmin_client.get_activity_stream(
                    token_json, activity.source_activity_id
                )
            except GarminActivityStreamNotFoundError:
                logger.warning(
                    "Skipping missing Garmin streams for activity.",
                    extra={
                        "sync_job.id": sync_job_id,
                        "user.id": user_id,
                        "activity.source_id": activity.source_activity_id,
                    },
                )
            else:
                self._upsert_stream(activity=activity, payload=stream_payload)
            imported_count += 1
            latest_checkpoint_value = self._max_checkpoint_value(
                latest_checkpoint_value,
                self._to_checkpoint_value(activity.start_date_utc),
            )
            self.sync_jobs.update_progress(
                sync_job, completed=index, total=len(activities_payload)
            )
            self.session.commit()
            logger.info(
                "Imported activity.",
                extra={
                    "sync_job.id": sync_job_id,
                    "user.id": user_id,
                    "activity.source_id": activity.source_activity_id,
                    "progress.completed": index,
                    "progress.total": len(activities_payload),
                },
            )

        self.checkpoints.upsert(
            user_id=user_id,
            sync_type=ACTIVITY_CHECKPOINT_TYPE,
            checkpoint_value=latest_checkpoint_value,
            last_synced_at=datetime.now(UTC),
        )
        rebuild_required = (
            imported_count > 0
            or self._analytics_rebuild_required(user_id)
            or (sync_job.metadata_json or {}).get("source") == "manual_refresh"
        )
        route_rebuild_required = (
            imported_count > 0
            or self._route_rebuild_required(user_id)
            or (sync_job.metadata_json or {}).get("source") == "manual_refresh"
        )
        if rebuild_required:
            source_run_efforts = self._load_source_run_efforts()
            self.read_model_builder.rebuild_for_user(
                user_id, source_run_efforts=source_run_efforts
            )
            self.checkpoints.upsert(
                user_id=user_id,
                sync_type=ANALYTICS_CHECKPOINT_TYPE,
                checkpoint_value=ANALYTICS_MODEL_VERSION,
                last_synced_at=datetime.now(UTC),
            )
        else:
            logger.info(
                "Skipping unchanged read-model rebuild.",
                extra={"sync_job.id": sync_job_id, "user.id": user_id},
            )
        route_stats = (
            self._rebuild_local_routes(user_id)
            if route_rebuild_required
            else None
        )
        if imported_count > 0 or rebuild_required or route_stats is not None:
            self.cache_invalidator.invalidate_user(user_id)
        self.sync_jobs.complete(sync_job, imported_activities=imported_count)
        self.session.commit()
        logger.info(
            "Completed import service run.",
            extra={
                "sync_job.id": sync_job_id,
                "user.id": user_id,
                "imported_count": imported_count,
                "checkpoint": latest_checkpoint_value,
                "route_group_count": (
                    None if route_stats is None else route_stats.route_group_count
                ),
                "read_models_rebuilt": rebuild_required,
                "routes_rebuilt": route_stats is not None,
            },
        )
        return imported_count

    def _get_garmin_credentials(self, user_id: int) -> str:
        credential = self.garmin_credentials.get_for_user(user_id)
        if credential is None:
            raise ValueError("Garmin credentials not found for user.")
        return self.token_cipher.decrypt(credential.token_json_encrypted)

    def _get_existing_checkpoint_value(self, user_id: int) -> str | None:
        checkpoint = self.checkpoints.get_for_user(user_id, ACTIVITY_CHECKPOINT_TYPE)
        if checkpoint is None:
            return None
        return checkpoint.checkpoint_value

    def _upsert_activity(self, *, user_id: int, payload: dict) -> Activity:
        activity = self.activities.get_by_source_activity_id(user_id, payload["id"])
        if activity is None:
            activity = Activity(
                user_id=user_id,
                source_activity_id=payload["id"],
                source_provider="garmin",
                name=payload.get("name") or "Unnamed activity",
                sport_type=payload["type"],
                start_date_utc=self._parse_datetime(
                    self._first_present(
                        payload, "start_date", "start_date_utc", "start_date_local"
                    )
                ),
            )
        activity.description = payload.get("description")
        activity.sport_type = payload["type"]
        activity.name = payload.get("name") or activity.name
        activity.start_date_utc = self._parse_datetime(self._first_present(payload, "start_date", "start_date_utc", "start_date_local"))  # type: ignore[assignment]
        activity.start_date_local = self._parse_datetime(
            payload.get("start_date_local") or payload.get("start_date")
        )
        activity.distance_meters = Decimal(
            str(self._first_present(payload, "distance", "distance_meters") or 0)
        )
        activity.moving_time_seconds = int(
            self._first_present(payload, "moving_time", "moving_time_seconds") or 0
        )
        activity.elapsed_time_seconds = (
            self._first_present(payload, "elapsed_time", "elapsed_time_seconds")
            or activity.moving_time_seconds
        )
        activity.total_elevation_gain_meters = self._decimal_or_none(
            self._first_present(
                payload, "total_elevation_gain", "total_elevation_gain_meters"
            )
        )
        activity.average_speed_mps = self._decimal_or_none(
            self._first_present(payload, "average_moving_speed", "average_speed"),
            scale=4,
        )
        if activity.average_speed_mps is None:
            activity.average_speed_mps = average_speed_mps(
                activity.distance_meters, activity.moving_time_seconds
            )
        activity.average_speed_kph = speed_kph(activity.average_speed_mps)
        activity.max_speed_mps = self._decimal_or_none(
            self._first_present(payload, "max_speed", "max_speed_mps"), scale=4
        )
        activity.average_heartrate_bpm = self._decimal_or_none(
            self._first_present(payload, "average_heartrate", "avg_hr", "average_hr")
        )
        activity.average_cadence = self._decimal_or_none(
            self._first_present(payload, "average_cadence", "avg_cadence")
        )
        activity.distance_km = distance_km(activity.distance_meters)
        activity.moving_time_display = format_moving_time(activity.moving_time_seconds)
        activity.average_pace_seconds_per_km = pace_seconds_per_km(
            activity.distance_meters,
            activity.moving_time_seconds,
            activity.sport_type,
        )
        activity.average_pace_display = format_pace(
            activity.average_pace_seconds_per_km
        )
        activity.summary_metric_display = summary_metric_display(
            activity.sport_type,
            pace_display=activity.average_pace_display,
            speed_kph_value=activity.average_speed_kph,
        )
        return self.activities.save(activity)

    def _upsert_stream(self, *, activity: Activity, payload: dict) -> ActivityStream:
        sanitized = sanitize_stream_payload(payload, activity.sport_type)
        activity_stream = self.activity_streams.get_by_activity_id(activity.id)
        if activity_stream is None:
            activity_stream = ActivityStream(activity_id=activity.id)
        activity_stream.time_stream = sanitized.get("time")
        activity_stream.distance_stream = sanitized.get("distance")
        activity_stream.latlng_stream = sanitized.get("latlng")
        activity_stream.altitude_stream = sanitized.get("altitude")
        activity_stream.velocity_smooth_stream = sanitized.get("velocity_smooth")
        activity_stream.heartrate_stream = sanitized.get("heartrate")
        speed_values = [
            value
            for value in (activity_stream.velocity_smooth_stream or {}).get("data", [])
            if isinstance(value, int | float) and not isinstance(value, bool)
        ]
        if speed_values:
            activity.max_speed_mps = self._decimal_or_none(max(speed_values), scale=4)
        return self.activity_streams.save(activity_stream)

    def _existing_activity_needs_stream_backfill(
            self, *, user_id: int, source_activity_id: int
    ) -> bool:
        activity = self.activities.get_by_source_activity_id(
            user_id, source_activity_id
        )
        if activity is None:
            return False
        stream = self.activity_streams.get_by_activity_id(activity.id)
        if stream is None:
            return True
        return not any(
            stream_value
            for stream_value in (
                stream.time_stream,
                stream.distance_stream,
                stream.latlng_stream,
                stream.altitude_stream,
                stream.velocity_smooth_stream,
                stream.heartrate_stream,
            )
        )

    def _load_source_run_efforts(self, **_: str) -> dict[int, dict[str, int]]:
        return {}

    def _analytics_rebuild_required(self, user_id: int) -> bool:
        checkpoint = self.checkpoints.get_for_user(user_id, ANALYTICS_CHECKPOINT_TYPE)
        return (
            checkpoint is None or checkpoint.checkpoint_value != ANALYTICS_MODEL_VERSION
        )

    def _route_rebuild_required(self, user_id: int) -> bool:
        checkpoint = self.checkpoints.get_for_user(user_id, ROUTE_CHECKPOINT_TYPE)
        return checkpoint is None or checkpoint.checkpoint_value != ROUTE_MODEL_VERSION

    def _rebuild_local_routes(self, user_id: int) -> RouteIndexStats | None:
        try:
            with self.session.begin_nested():
                stats = self.route_index_builder.rebuild_for_user(user_id)
                self.checkpoints.upsert(
                    user_id=user_id,
                    sync_type=ROUTE_CHECKPOINT_TYPE,
                    checkpoint_value=ROUTE_MODEL_VERSION,
                    last_synced_at=datetime.now(UTC),
                )
                return stats
        except Exception:
            logger.exception(
                "Local route index rebuild failed; preserving the previous route index.",
                extra={"user.id": user_id},
            )
            return None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed

    @staticmethod
    def _decimal_or_none(
        value: float | int | None, *, scale: int = 2
    ) -> Decimal | None:
        if value is None:
            return None
        quantize_value = "0." + ("0" * (scale - 1)) + "1"
        return Decimal(str(value)).quantize(Decimal(quantize_value))

    @staticmethod
    def _first_present(payload: dict, *keys: str):
        for key in keys:
            if payload.get(key) is not None:
                return payload[key]
        return None

    @staticmethod
    def _to_checkpoint_value(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _max_checkpoint_value(current: str | None, candidate: str | None) -> str | None:
        if candidate is None:
            return current
        if current is None:
            return candidate
        current_dt = BaseImportService._parse_datetime(current)
        candidate_dt = BaseImportService._parse_datetime(candidate)
        if current_dt is None:
            return candidate
        if candidate_dt is None:
            return current
        return candidate if candidate_dt >= current_dt else current


class FullImportService(BaseImportService):
    def run(self, *, sync_job_id: int, user_id: int) -> int:
        return self._run(sync_job_id=sync_job_id, user_id=user_id, after=None)


class IncrementalSyncService(BaseImportService):
    def run(self, *, sync_job_id: int, user_id: int) -> int:
        checkpoint = self.checkpoints.get_for_user(user_id, ACTIVITY_CHECKPOINT_TYPE)
        if checkpoint is not None:
            after = self._parse_datetime(checkpoint.checkpoint_value)
        else:
            after = self.activities.get_latest_start_date_utc_for_user(user_id)
        return self._run(sync_job_id=sync_job_id, user_id=user_id, after=after)
