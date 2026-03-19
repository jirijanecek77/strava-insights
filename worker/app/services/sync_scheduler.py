import logging

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.repositories import SyncJobRepository, UserRepository


logger = logging.getLogger(__name__)


class DailyIncrementalSyncScheduler:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sync_jobs = SyncJobRepository(session)

    def run(self) -> int:
        scheduled_jobs = 0
        candidate_user_ids = self.users.list_incremental_sync_candidates()
        logger.info("Loaded incremental sync candidates.", extra={"candidate_count": len(candidate_user_ids)})
        for user_id in candidate_user_ids:
            active_job = self.sync_jobs.get_active_for_user(user_id)
            if active_job is not None:
                logger.info("Skipping scheduled sync because an active job exists.", extra={"user.id": user_id})
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
            logger.info(
                "Scheduled incremental sync job.",
                extra={"user.id": user_id, "sync_job.id": sync_job.id},
            )
            scheduled_jobs += 1

        return scheduled_jobs
