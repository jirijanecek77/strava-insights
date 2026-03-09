from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.repositories import SyncJobRepository, UserRepository


class DailyIncrementalSyncScheduler:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sync_jobs = SyncJobRepository(session)

    def run(self) -> int:
        scheduled_jobs = 0
        for user_id in self.users.list_incremental_sync_candidates():
            active_job = self.sync_jobs.get_active_for_user(user_id)
            if active_job is not None:
                continue

            sync_job = self.sync_jobs.create_queued(
                user_id=user_id,
                sync_type="incremental_sync",
                metadata_json={"source": "daily_schedule"},
            )
            celery_app.send_task(
                "app.tasks.sync.run_incremental_sync",
                kwargs={"sync_job_id": sync_job.id, "user_id": user_id},
            )
            scheduled_jobs += 1

        return scheduled_jobs
