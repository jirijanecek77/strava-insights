import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy.orm import Session

from app.intervals_client import (
    IntervalsActivityStreamNotFoundError,
    IntervalsApiClient,
)
from app.models import Activity, ActivityStream
from app.repositories import (
    ActivityRepository,
    ActivityStreamRepository,
    IntervalsCredentialRepository,
    SyncCheckpointRepository,
    SyncJobRepository,
)
from app.security import TokenCipher
from app.services.activity_import_writer import ActivityImportWriter
from app.services.cache_invalidator import UserCacheInvalidator
from app.services.read_model_builder import RUN_BEST_EFFORT_DISTANCES, ReadModelBuilder
from app.services.local_route_matcher import ROUTE_MODEL_VERSION
from app.services.route_index_builder import RouteIndexBuilder, RouteIndexStats

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
        intervals_client: IntervalsApiClient | None = None,
        token_cipher: TokenCipher | None = None,
    ) -> None:
        self.session = session
        self.intervals_client = intervals_client or IntervalsApiClient()
        self.token_cipher = token_cipher or TokenCipher()
        self.intervals_credentials = IntervalsCredentialRepository(session)
        self.sync_jobs = SyncJobRepository(session)
        self.activities = ActivityRepository(session)
        self.activity_streams = ActivityStreamRepository(session)
        self.activity_writer = ActivityImportWriter(
            activities=self.activities, activity_streams=self.activity_streams
        )
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

        athlete_id, api_key = self._get_intervals_credentials(user_id)
        activities_payload = [
            activity
            for activity in self.intervals_client.get_activities(
                athlete_id, api_key, after=after
            )
            if activity.get("type") in SUPPORTED_SPORTS
        ]
        for fetched_activity in activities_payload:
            fetched_activity["id"] = self.intervals_client.parse_activity_id(
                fetched_activity["id"]
            )
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
        ]
        logger.info(
            "Fetched Intervals.icu activities for import.",
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
                stream_payload = self.intervals_client.get_activity_stream(
                    api_key, activity.strava_activity_id
                )
            except IntervalsActivityStreamNotFoundError:
                logger.warning(
                    "Skipping missing Intervals.icu streams for activity.",
                    extra={
                        "sync_job.id": sync_job_id,
                        "user.id": user_id,
                        "activity.source_id": activity.strava_activity_id,
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
                    "activity.source_id": activity.strava_activity_id,
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
            source_run_efforts = self._load_source_run_efforts(
                athlete_id=athlete_id, api_key=api_key
            )
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
            self._rebuild_local_routes(user_id) if route_rebuild_required else None
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

    def _get_intervals_credentials(self, user_id: int) -> tuple[str, str]:
        credential = self.intervals_credentials.get_for_user(user_id)
        if credential is None:
            raise ValueError("Intervals.icu credentials not found for user.")

        return credential.athlete_id, self.token_cipher.decrypt(
            credential.api_key_encrypted
        )

    def _get_existing_checkpoint_value(self, user_id: int) -> str | None:
        checkpoint = self.checkpoints.get_for_user(user_id, ACTIVITY_CHECKPOINT_TYPE)
        if checkpoint is None:
            return None
        return checkpoint.checkpoint_value

    def _upsert_activity(self, *, user_id: int, payload: dict) -> Activity:
        self.activity_writer = ActivityImportWriter(
            activities=self.activities, activity_streams=self.activity_streams
        )
        return self.activity_writer.upsert_activity(user_id=user_id, payload=payload)

    def _upsert_stream(self, *, activity: Activity, payload: dict) -> ActivityStream:
        self.activity_writer = ActivityImportWriter(
            activities=self.activities, activity_streams=self.activity_streams
        )
        return self.activity_writer.upsert_stream(activity=activity, payload=payload)

    def _load_source_run_efforts(
        self, *, athlete_id: str, api_key: str
    ) -> dict[int, dict[str, int]]:
        requested_distances = list(RUN_BEST_EFFORT_DISTANCES.values())
        try:
            payload = self.intervals_client.get_run_pace_curves(
                athlete_id,
                api_key,
                distances_meters=requested_distances,
            )
        except (httpx.HTTPError, ValueError):
            logger.warning(
                "Intervals.icu pace curves are unavailable; using linear local best-effort calculation.",
                exc_info=True,
            )
            return {}

        response_distances = payload.get("distances") or requested_distances
        code_by_distance = {
            distance: code for code, distance in RUN_BEST_EFFORT_DISTANCES.items()
        }
        efforts: dict[int, dict[str, int]] = {}
        for curve in payload.get("curves", []):
            if (
                not isinstance(curve, dict)
                or curve.get("id") is None
                or not isinstance(curve.get("secs"), list)
            ):
                continue
            source_activity_id = self.intervals_client.parse_activity_id(curve["id"])
            activity_efforts: dict[str, int] = {}
            for distance, seconds in zip(response_distances, curve["secs"]):
                effort_code = next(
                    (
                        code
                        for known_distance, code in code_by_distance.items()
                        if abs(float(distance) - known_distance) < 0.01
                    ),
                    None,
                )
                if (
                    effort_code is None
                    or not isinstance(seconds, int | float)
                    or seconds <= 0
                ):
                    continue
                activity_efforts[effort_code] = round(seconds)
            efforts[source_activity_id] = activity_efforts
        return efforts

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
        return ActivityImportWriter.parse_datetime(value)

    @staticmethod
    def _decimal_or_none(value: float | int | None, *, scale: int = 2):
        return ActivityImportWriter.decimal_or_none(value, scale=scale)

    @staticmethod
    def _first_present(payload: dict, *keys: str):
        return ActivityImportWriter.first_present(payload, *keys)

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
