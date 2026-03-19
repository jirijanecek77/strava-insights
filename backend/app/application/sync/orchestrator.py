import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.sync.dto import CreatedSyncJob
from app.infrastructure.db.models.sync_job import SyncJob
from app.infrastructure.queue.celery_client import CeleryQueueClient
from app.infrastructure.repositories.sync_job_repository import SyncJobRepository


logger = logging.getLogger(__name__)


class SyncOrchestrator:
    def __init__(
        self,
        db_session: Session = Depends(get_db_session),
        queue_client: CeleryQueueClient = Depends(CeleryQueueClient),
    ) -> None:
        self.db_session = db_session
        self.sync_job_repository = SyncJobRepository(db_session)
        self.queue_client = queue_client

    def enqueue_first_import_if_needed(self, user_id: int) -> CreatedSyncJob | None:
        latest_job = self.sync_job_repository.get_latest_for_user(user_id)
        if latest_job is not None:
            logger.info("Skipping first import enqueue because a sync job already exists.", extra={"user.id": user_id})
            return None

        return self._enqueue_job(
            user_id=user_id,
            sync_type="full_import",
            metadata={"source": "auth_callback"},
        )

    def enqueue_incremental_sync(self, user_id: int) -> CreatedSyncJob:
        active_job = self.sync_job_repository.get_active_for_user(user_id)
        if active_job is not None:
            logger.info(
                "Returning existing active sync job.",
                extra={"user.id": user_id, "sync_job.id": active_job.id, "sync_type": active_job.sync_type},
            )
            return CreatedSyncJob(
                id=active_job.id,
                user_id=user_id,
                sync_type=active_job.sync_type,
                status=active_job.status,
            )

        return self._enqueue_job(
            user_id=user_id,
            sync_type="incremental_sync",
            metadata={"source": "manual_refresh"},
        )

    def _enqueue_job(self, *, user_id: int, sync_type: str, metadata: dict[str, str]) -> CreatedSyncJob:
        logger.info("Creating sync job.", extra={"user.id": user_id, "sync_type": sync_type, "metadata": metadata})
        sync_job = SyncJob(
            user_id=user_id,
            status="queued",
            sync_type=sync_type,
            progress_total=1,
            progress_completed=0,
            metadata_json=metadata,
        )
        self.sync_job_repository.save(sync_job)
        self.db_session.commit()
        self.db_session.refresh(sync_job)
        logger.info(
            "Persisted sync job.",
            extra={"user.id": user_id, "sync_job.id": sync_job.id, "sync_type": sync_type},
        )

        if sync_type == "full_import":
            self.queue_client.enqueue_full_import(sync_job_id=sync_job.id, user_id=user_id)
        else:
            self.queue_client.enqueue_incremental_sync(sync_job_id=sync_job.id, user_id=user_id)
        logger.info(
            "Enqueued sync job to Celery.",
            extra={"user.id": user_id, "sync_job.id": sync_job.id, "sync_type": sync_type},
        )

        return CreatedSyncJob(
            id=sync_job.id,
            user_id=user_id,
            sync_type=sync_job.sync_type,
            status=sync_job.status,
        )
