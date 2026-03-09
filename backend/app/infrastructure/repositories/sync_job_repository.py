from sqlalchemy.orm import Session

from app.infrastructure.db.models.sync_job import SyncJob


class SyncJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_latest_for_user(self, user_id: int) -> SyncJob | None:
        return (
            self.session.query(SyncJob)
            .filter(SyncJob.user_id == user_id)
            .order_by(SyncJob.created_at.desc())
            .first()
        )

    def get_by_id(self, sync_job_id: int) -> SyncJob | None:
        return self.session.query(SyncJob).filter(SyncJob.id == sync_job_id).one_or_none()

    def get_active_for_user(self, user_id: int) -> SyncJob | None:
        return (
            self.session.query(SyncJob)
            .filter(SyncJob.user_id == user_id, SyncJob.status.in_(("queued", "running")))
            .order_by(SyncJob.created_at.desc())
            .first()
        )

    def save(self, sync_job: SyncJob) -> SyncJob:
        self.session.add(sync_job)
        self.session.flush()
        return sync_job
