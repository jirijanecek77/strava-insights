from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import (
    Activity,
    ActivityBestEffort,
    ActivityStream,
    BestEffort,
    OauthToken,
    PeriodSummary,
    SyncCheckpoint,
    SyncJob,
    User,
    UserProfile,
)


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_incremental_sync_candidates(self) -> list[int]:
        rows = (
            self.session.query(User.id)
            .join(OauthToken, OauthToken.user_id == User.id)
            .filter(User.is_active.is_(True), OauthToken.provider == "strava")
            .distinct()
            .all()
        )
        return [user_id for (user_id,) in rows]


class UserProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> UserProfile | None:
        return self.session.query(UserProfile).filter(UserProfile.user_id == user_id).one_or_none()


class OauthTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int, provider: str = "strava") -> OauthToken | None:
        return (
            self.session.query(OauthToken)
            .filter(OauthToken.user_id == user_id, OauthToken.provider == provider)
            .one_or_none()
        )


class SyncJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, sync_job_id: int, user_id: int) -> SyncJob | None:
        return (
            self.session.query(SyncJob)
            .filter(SyncJob.id == sync_job_id, SyncJob.user_id == user_id)
            .one_or_none()
        )

    def get_active_for_user(self, user_id: int) -> SyncJob | None:
        return (
            self.session.query(SyncJob)
            .filter(SyncJob.user_id == user_id, SyncJob.status.in_(("queued", "running")))
            .order_by(SyncJob.created_at.desc())
            .first()
        )

    def create_queued(self, *, user_id: int, sync_type: str, metadata_json: dict | None = None) -> SyncJob:
        sync_job = SyncJob(
            user_id=user_id,
            status="queued",
            sync_type=sync_type,
            progress_total=1,
            progress_completed=0,
            metadata_json=metadata_json,
        )
        self.session.add(sync_job)
        self.session.flush()
        return sync_job

    def update_running(self, sync_job: SyncJob, *, progress_total: int | None) -> None:
        sync_job.status = "running"
        sync_job.started_at = datetime.now(UTC)
        sync_job.progress_total = progress_total
        sync_job.progress_completed = 0
        sync_job.metadata_json = {**(sync_job.metadata_json or {}), "phase": "importing"}
        self.session.flush()

    def update_progress(self, sync_job: SyncJob, *, completed: int, total: int) -> None:
        sync_job.progress_completed = completed
        sync_job.progress_total = total
        self.session.flush()

    def complete(self, sync_job: SyncJob, *, imported_activities: int) -> None:
        sync_job.status = "completed"
        sync_job.finished_at = datetime.now(UTC)
        sync_job.progress_completed = imported_activities
        sync_job.progress_total = imported_activities
        sync_job.metadata_json = {
            **(sync_job.metadata_json or {}),
            "phase": "completed",
            "imported_activities": imported_activities,
        }
        self.session.flush()

    def fail(self, sync_job: SyncJob, *, error_message: str) -> None:
        sync_job.status = "failed"
        sync_job.finished_at = datetime.now(UTC)
        sync_job.error_message = error_message
        self.session.flush()


class ActivityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, activity_id: int) -> Activity | None:
        return self.session.query(Activity).filter(Activity.id == activity_id).one_or_none()

    def get_by_strava_id(self, user_id: int, strava_activity_id: int) -> Activity | None:
        return (
            self.session.query(Activity)
            .filter(Activity.user_id == user_id, Activity.strava_activity_id == strava_activity_id)
            .one_or_none()
        )

    def list_existing_strava_ids_for_user(self, user_id: int, strava_activity_ids: list[int]) -> set[int]:
        if not strava_activity_ids:
            return set()
        rows = (
            self.session.query(Activity.strava_activity_id)
            .filter(Activity.user_id == user_id, Activity.strava_activity_id.in_(strava_activity_ids))
            .all()
        )
        return {strava_activity_id for (strava_activity_id,) in rows}

    def save(self, activity: Activity) -> Activity:
        self.session.add(activity)
        self.session.flush()
        return activity

    def list_for_user(self, user_id: int, sport_type: str | None = None) -> list[Activity]:
        query = self.session.query(Activity).filter(Activity.user_id == user_id)
        if sport_type is not None:
            query = query.filter(Activity.sport_type == sport_type)
        return query.order_by(Activity.start_date_local.asc()).all()

    def get_latest_start_date_utc_for_user(self, user_id: int) -> datetime | None:
        row = (
            self.session.query(Activity.start_date_utc)
            .filter(Activity.user_id == user_id)
            .order_by(Activity.start_date_utc.desc())
            .first()
        )
        if row is None:
            return None
        return row[0]


class ActivityStreamRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_activity_id(self, activity_id: int) -> ActivityStream | None:
        return self.session.query(ActivityStream).filter(ActivityStream.activity_id == activity_id).one_or_none()

    def save(self, activity_stream: ActivityStream) -> ActivityStream:
        self.session.add(activity_stream)
        self.session.flush()
        return activity_stream

    def get_by_activity_ids(self, activity_ids: list[int]) -> list[ActivityStream]:
        if not activity_ids:
            return []
        return self.session.query(ActivityStream).filter(ActivityStream.activity_id.in_(activity_ids)).all()


class PeriodSummaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_user(self, *, user_id: int, summaries: list[PeriodSummary]) -> None:
        self.session.query(PeriodSummary).filter(PeriodSummary.user_id == user_id).delete()
        if summaries:
            self.session.add_all(summaries)
        self.session.flush()


class BestEffortRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_user(self, *, user_id: int, efforts: list[BestEffort]) -> None:
        self.session.query(BestEffort).filter(BestEffort.user_id == user_id).delete()
        if efforts:
            self.session.add_all(efforts)
        self.session.flush()


class ActivityBestEffortRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_activities(self, *, activity_ids: list[int], efforts: list[ActivityBestEffort]) -> None:
        if activity_ids:
            self.session.query(ActivityBestEffort).filter(ActivityBestEffort.activity_id.in_(activity_ids)).delete(
                synchronize_session=False
            )
        if efforts:
            self.session.add_all(efforts)
        self.session.flush()


class SyncCheckpointRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int, sync_type: str) -> SyncCheckpoint | None:
        return (
            self.session.query(SyncCheckpoint)
            .filter(SyncCheckpoint.user_id == user_id, SyncCheckpoint.sync_type == sync_type)
            .one_or_none()
        )

    def upsert(self, *, user_id: int, sync_type: str, checkpoint_value: str | None, last_synced_at: datetime | None) -> None:
        checkpoint = self.get_for_user(user_id, sync_type)
        if checkpoint is None:
            checkpoint = SyncCheckpoint(
                user_id=user_id,
                sync_type=sync_type,
                checkpoint_value=checkpoint_value,
                last_synced_at=last_synced_at,
            )
            self.session.add(checkpoint)
        else:
            checkpoint.checkpoint_value = checkpoint_value
            checkpoint.last_synced_at = last_synced_at
        self.session.flush()
