import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Activity, ActivityStream
from app.repositories import (
    ActivityRepository,
    ActivityStreamRepository,
    OauthTokenRepository,
    SyncCheckpointRepository,
    SyncJobRepository,
    UserStravaAppCredentialRepository,
)
from app.security import TokenCipher
from app.services.activity_summary import (
    distance_km,
    format_moving_time,
    format_pace,
    pace_seconds_per_km,
    speed_kph,
    summary_metric_display,
)
from app.services.cache_invalidator import UserCacheInvalidator
from app.services.heart_rate_drift import calculate_heart_rate_drift_bpm
from app.services.read_model_builder import ReadModelBuilder
from app.strava_client import StravaActivityStreamNotFoundError, StravaApiClient


SUPPORTED_SPORTS = {"Run", "Ride", "EBikeRide"}
ACTIVITY_CHECKPOINT_TYPE = "activities"
logger = logging.getLogger(__name__)


class BaseImportService:
    def __init__(
        self,
        session: Session,
        *,
        strava_client: StravaApiClient | None = None,
        token_cipher: TokenCipher | None = None,
    ) -> None:
        self.session = session
        self.strava_client = strava_client or StravaApiClient()
        self.token_cipher = token_cipher or TokenCipher()
        self.oauth_tokens = OauthTokenRepository(session)
        self.strava_app_credentials = UserStravaAppCredentialRepository(session)
        self.sync_jobs = SyncJobRepository(session)
        self.activities = ActivityRepository(session)
        self.activity_streams = ActivityStreamRepository(session)
        self.checkpoints = SyncCheckpointRepository(session)
        self.cache_invalidator = UserCacheInvalidator()
        self.read_model_builder = ReadModelBuilder(session)

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

        access_token = self._get_access_token(user_id)
        activities_payload = [
            activity
            for activity in self.strava_client.get_activities(access_token, after=after)
            if activity.get("type") in SUPPORTED_SPORTS
        ]
        existing_strava_ids = self.activities.list_existing_strava_ids_for_user(
            user_id,
            [activity["id"] for activity in activities_payload if activity.get("id") is not None],
        )
        activities_payload = [
            activity for activity in activities_payload if activity.get("id") not in existing_strava_ids
        ]
        logger.info(
            "Fetched Strava activities for import.",
            extra={
                "sync_job.id": sync_job_id,
                "user.id": user_id,
                "fetched_count": len(activities_payload),
                "existing_count": len(existing_strava_ids),
            },
        )
        self.sync_jobs.update_running(sync_job, progress_total=len(activities_payload))
        self.session.commit()

        imported_count = 0
        latest_checkpoint_value = self._get_existing_checkpoint_value(user_id)

        for index, activity_payload in enumerate(activities_payload, start=1):
            activity = self._upsert_activity(user_id=user_id, payload=activity_payload)
            try:
                stream_payload = self.strava_client.get_activity_stream(access_token, activity.strava_activity_id)
            except StravaActivityStreamNotFoundError:
                logger.warning(
                    "Skipping missing Strava streams for activity.",
                    extra={
                        "sync_job.id": sync_job_id,
                        "user.id": user_id,
                        "activity.strava_id": activity.strava_activity_id,
                    },
                )
            else:
                self._upsert_stream(activity_id=activity.id, payload=stream_payload)
            imported_count += 1
            latest_checkpoint_value = self._max_checkpoint_value(
                latest_checkpoint_value,
                self._to_checkpoint_value(activity.start_date_utc),
            )
            self.sync_jobs.update_progress(sync_job, completed=index, total=len(activities_payload))
            self.session.commit()
            logger.info(
                "Imported activity.",
                extra={
                    "sync_job.id": sync_job_id,
                    "user.id": user_id,
                    "activity.strava_id": activity.strava_activity_id,
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
        self.read_model_builder.rebuild_for_user(user_id)
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
            },
        )
        return imported_count

    def _get_access_token(self, user_id: int) -> str:
        oauth_token = self.oauth_tokens.get_for_user(user_id)
        if oauth_token is None:
            raise ValueError("OAuth token not found for user.")
        app_credential = self.strava_app_credentials.get_for_user(user_id)
        if app_credential is None:
            raise ValueError("Strava app credentials not found for user.")

        access_token = self.token_cipher.decrypt(oauth_token.access_token_encrypted)
        if oauth_token.expires_at <= datetime.now(UTC):
            logger.info("Refreshing expired Strava access token.", extra={"user.id": user_id})
            refresh_payload = self.strava_client.refresh_access_token(
                self.token_cipher.decrypt(oauth_token.refresh_token_encrypted),
                client_id=app_credential.client_id,
                client_secret=self.token_cipher.decrypt(app_credential.client_secret_encrypted),
            )
            oauth_token.access_token_encrypted = self.token_cipher.encrypt(refresh_payload["access_token"])
            oauth_token.refresh_token_encrypted = self.token_cipher.encrypt(refresh_payload["refresh_token"])
            oauth_token.expires_at = self.strava_client.parse_expires_at(refresh_payload)
            oauth_token.scope = refresh_payload.get("scope")
            access_token = refresh_payload["access_token"]
            self.session.flush()
            logger.info("Refreshed Strava access token.", extra={"user.id": user_id})
        return access_token

    def _get_existing_checkpoint_value(self, user_id: int) -> str | None:
        checkpoint = self.checkpoints.get_for_user(user_id, ACTIVITY_CHECKPOINT_TYPE)
        if checkpoint is None:
            return None
        return checkpoint.checkpoint_value

    def _upsert_activity(self, *, user_id: int, payload: dict) -> Activity:
        activity = self.activities.get_by_strava_id(user_id, payload["id"])
        if activity is None:
            activity = Activity(
                user_id=user_id,
                strava_activity_id=payload["id"],
                name=payload.get("name") or "Unnamed activity",
                sport_type=payload["type"],
                start_date_utc=self._parse_datetime(payload["start_date"]),
            )
        activity.description = payload.get("description")
        activity.sport_type = payload["type"]
        activity.name = payload.get("name") or activity.name
        activity.start_date_utc = self._parse_datetime(payload["start_date"])
        activity.start_date_local = self._parse_datetime(payload.get("start_date_local"))
        activity.distance_meters = Decimal(str(payload.get("distance") or 0))
        activity.moving_time_seconds = int(payload.get("moving_time") or 0)
        activity.elapsed_time_seconds = payload.get("elapsed_time")
        activity.total_elevation_gain_meters = self._decimal_or_none(payload.get("total_elevation_gain"))
        activity.elev_high_meters = self._decimal_or_none(payload.get("elev_high"))
        activity.elev_low_meters = self._decimal_or_none(payload.get("elev_low"))
        activity.average_speed_mps = self._decimal_or_none(payload.get("average_speed"), scale=4)
        activity.average_speed_kph = speed_kph(activity.average_speed_mps)
        activity.max_speed_mps = self._decimal_or_none(payload.get("max_speed"), scale=4)
        activity.average_heartrate_bpm = self._decimal_or_none(payload.get("average_heartrate"))
        activity.max_heartrate_bpm = payload.get("max_heartrate")
        activity.average_cadence = self._decimal_or_none(payload.get("average_cadence"))
        activity.distance_km = distance_km(activity.distance_meters)
        activity.moving_time_display = format_moving_time(activity.moving_time_seconds)
        activity.average_pace_seconds_per_km = pace_seconds_per_km(
            activity.distance_meters,
            activity.moving_time_seconds,
            activity.sport_type,
        )
        activity.average_pace_display = format_pace(activity.average_pace_seconds_per_km)
        activity.summary_metric_display = summary_metric_display(
            activity.sport_type,
            pace_display=activity.average_pace_display,
            speed_kph_value=activity.average_speed_kph,
        )
        start_latlng = payload.get("start_latlng")
        activity.start_latlng = list(start_latlng) if start_latlng else None
        return self.activities.save(activity)

    def _upsert_stream(self, *, activity_id: int, payload: dict) -> ActivityStream:
        activity_stream = self.activity_streams.get_by_activity_id(activity_id)
        if activity_stream is None:
            activity_stream = ActivityStream(activity_id=activity_id)
        activity_stream.time_stream = payload.get("time")
        activity_stream.distance_stream = payload.get("distance")
        activity_stream.latlng_stream = payload.get("latlng")
        activity_stream.altitude_stream = payload.get("altitude")
        activity_stream.velocity_smooth_stream = payload.get("velocity_smooth")
        activity_stream.heartrate_stream = payload.get("heartrate")
        saved_stream = self.activity_streams.save(activity_stream)
        activity = self.activities.get_by_id(activity_id)
        if activity is not None:
            activity.heart_rate_drift_bpm = calculate_heart_rate_drift_bpm(
                distance_stream_meters=(saved_stream.distance_stream or {}).get("data", []),
                heartrate_stream_bpm=(saved_stream.heartrate_stream or {}).get("data", []),
            )
            self.activities.save(activity)
        return saved_stream

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _decimal_or_none(value: float | int | None, *, scale: int = 2) -> Decimal | None:
        if value is None:
            return None
        quantize_value = "0." + ("0" * (scale - 1)) + "1"
        return Decimal(str(value)).quantize(Decimal(quantize_value))

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
