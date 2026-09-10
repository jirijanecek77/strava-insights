from app.models import (
    Activity,
    ActivityRouteMembership,
    ActivityRouteSignature,
    ActivityStream,
    BestEffort,
    GarminCredential,
    PeriodSummary,
    RouteGroup,
    SyncCheckpoint,
    SyncDispatchOutbox,
    SyncJob,
    User,
)
from datetime import UTC, datetime
from datetime import timedelta
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.query(User).filter(User.id == user_id).one_or_none()

    def list_incremental_sync_candidates(self) -> list[int]:
        rows = (
            self.session.query(User.id)
            .join(GarminCredential, GarminCredential.user_id == User.id)
            .filter(
                User.is_active.is_(True),
                GarminCredential.connection_status == "connected",
            )
            .distinct()
            .all()
        )
        return [user_id for (user_id,) in rows]


class GarminCredentialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> GarminCredential | None:
        return (
            self.session.query(GarminCredential)
            .filter(GarminCredential.user_id == user_id)
            .one_or_none()
        )

    def save(self, credential: GarminCredential) -> GarminCredential:
        self.session.add(credential)
        self.session.flush()
        return credential

    def mark_reauthentication_required(self, user_id: int) -> None:
        credential = self.get_for_user(user_id)
        if credential is None:
            return
        credential.connection_status = "reauthentication_required"
        self.session.flush()


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
            .filter(
                SyncJob.user_id == user_id, SyncJob.status.in_(("queued", "running"))
            )
            .order_by(SyncJob.created_at.desc())
            .first()
        )

    def claim_for_execution(self, *, sync_job_id: int, user_id: int) -> SyncJob | None:
        claimed = (
            self.session.query(SyncJob)
            .filter(
                SyncJob.id == sync_job_id,
                SyncJob.user_id == user_id,
                SyncJob.status == "queued",
            )
            .update(
                {
                    SyncJob.status: "running",
                    SyncJob.started_at: datetime.now(UTC),
                },
                synchronize_session=False,
            )
        )
        if claimed != 1:
            self.session.rollback()
            return None
        self.session.commit()
        return self.get(sync_job_id, user_id)

    def create_queued(
        self, *, user_id: int, sync_type: str, metadata_json: dict | None = None
    ) -> SyncJob:
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
        sync_job.metadata_json = {
            **(sync_job.metadata_json or {}),
            "phase": "importing",
        }
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

    def requeue_after_transient_failure(
            self, sync_job: SyncJob, *, error_message: str
    ) -> None:
        sync_job.status = "queued"
        sync_job.error_message = error_message[:1000]
        self.session.flush()

    def require_authentication(self, sync_job: SyncJob) -> None:
        sync_job.status = "authentication_required"
        sync_job.finished_at = datetime.now(UTC)
        sync_job.error_message = "Garmin connection expired. Sign in again, then start a sync."
        sync_job.metadata_json = {
            **(sync_job.metadata_json or {}),
            "phase": "authentication_required",
        }
        self.session.flush()


class SyncDispatchOutboxRepository:
    _LEASE_DURATION = timedelta(minutes=1)

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_sync_dispatch(
            self, *, sync_job_id: int, user_id: int, sync_type: str
    ) -> SyncDispatchOutbox:
        dispatch = SyncDispatchOutbox(
            sync_job_id=sync_job_id,
            user_id=user_id,
            sync_type=sync_type,
            payload_json={"sync_job_id": sync_job_id, "user_id": user_id},
            status="pending",
        )
        self.session.add(dispatch)
        self.session.flush()
        return dispatch

    def claim_pending(self, *, limit: int) -> list[SyncDispatchOutbox]:
        now = datetime.now(UTC)
        reclaimable = and_(
            SyncDispatchOutbox.status == "dispatching",
            SyncDispatchOutbox.lease_expires_at <= now,
        )
        pending = and_(
            SyncDispatchOutbox.status == "pending",
            or_(
                SyncDispatchOutbox.next_attempt_at.is_(None),
                SyncDispatchOutbox.next_attempt_at <= now,
            ),
        )
        dispatches = (
            self.session.query(SyncDispatchOutbox)
            .filter(or_(pending, reclaimable))
            .order_by(SyncDispatchOutbox.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(limit)
            .all()
        )
        for dispatch in dispatches:
            dispatch.status = "dispatching"
            dispatch.attempt_count += 1
            dispatch.lease_expires_at = now + self._LEASE_DURATION
        self.session.commit()
        return dispatches

    def mark_dispatched(self, dispatch: SyncDispatchOutbox) -> None:
        dispatch.status = "dispatched"
        dispatch.dispatched_at = datetime.now(UTC)
        dispatch.lease_expires_at = None
        dispatch.last_error = None
        self.session.commit()

    def reschedule_after_publish_failure(
            self, dispatch: SyncDispatchOutbox, *, error_message: str
    ) -> None:
        delay_seconds = min(300, 2 ** min(dispatch.attempt_count, 8))
        dispatch.status = "pending"
        dispatch.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        dispatch.lease_expires_at = None
        dispatch.last_error = error_message[:1000]
        self.session.commit()


class ActivityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_source_activity_id(
        self, user_id: int, source_activity_id: int, source_provider: str = "garmin"
    ) -> Activity | None:
        return (
            self.session.query(Activity)
            .filter(
                Activity.user_id == user_id,
                Activity.source_provider == source_provider,
                Activity.source_activity_id == source_activity_id,
            )
            .one_or_none()
        )

    def list_existing_source_activity_ids_for_user(
        self, user_id: int, source_activity_ids: list[int], source_provider: str = "garmin"
    ) -> set[int]:
        if not source_activity_ids:
            return set()
        rows = (
            self.session.query(Activity.source_activity_id)
            .filter(
                Activity.user_id == user_id,
                Activity.source_provider == source_provider,
                Activity.source_activity_id.in_(source_activity_ids),
            )
            .all()
        )
        return {source_activity_id for (source_activity_id,) in rows}

    def save(self, activity: Activity) -> Activity:
        self.session.add(activity)
        self.session.flush()
        return activity

    def list_for_user(
        self, user_id: int, sport_type: str | None = None
    ) -> list[Activity]:
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
        return (
            self.session.query(ActivityStream)
            .filter(ActivityStream.activity_id == activity_id)
            .one_or_none()
        )

    def save(self, activity_stream: ActivityStream) -> ActivityStream:
        self.session.add(activity_stream)
        self.session.flush()
        return activity_stream

    def get_by_activity_ids(self, activity_ids: list[int]) -> list[ActivityStream]:
        if not activity_ids:
            return []
        return (
            self.session.query(ActivityStream)
            .filter(ActivityStream.activity_id.in_(activity_ids))
            .all()
        )


class LocalRouteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_user(
        self,
        *,
        user_id: int,
        signatures: list[ActivityRouteSignature],
        groups: list[tuple[RouteGroup, list[ActivityRouteMembership]]],
    ) -> None:
        route_group_ids = [
            route_group_id
            for (route_group_id,) in self.session.query(RouteGroup.id)
            .filter(RouteGroup.user_id == user_id)
            .all()
        ]
        if route_group_ids:
            self.session.query(ActivityRouteMembership).filter(
                ActivityRouteMembership.route_group_id.in_(route_group_ids)
            ).delete(synchronize_session=False)
        self.session.query(RouteGroup).filter(RouteGroup.user_id == user_id).delete(
            synchronize_session=False
        )
        self.session.query(ActivityRouteSignature).filter(
            ActivityRouteSignature.user_id == user_id
        ).delete(synchronize_session=False)
        if signatures:
            self.session.add_all(signatures)
        for route_group, memberships in groups:
            self.session.add(route_group)
            self.session.flush()
            for membership in memberships:
                membership.route_group_id = route_group.id
            self.session.add_all(memberships)
        self.session.flush()


class PeriodSummaryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_user(self, *, user_id: int, summaries: list[PeriodSummary]) -> None:
        self.session.query(PeriodSummary).filter(
            PeriodSummary.user_id == user_id
        ).delete()
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


class SyncCheckpointRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int, sync_type: str) -> SyncCheckpoint | None:
        return (
            self.session.query(SyncCheckpoint)
            .filter(
                SyncCheckpoint.user_id == user_id, SyncCheckpoint.sync_type == sync_type
            )
            .one_or_none()
        )

    def upsert(
        self,
        *,
        user_id: int,
        sync_type: str,
        checkpoint_value: str | None,
        last_synced_at: datetime | None
    ) -> None:
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
