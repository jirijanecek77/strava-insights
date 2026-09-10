import logging

from app.celery_app import celery_app
from app.db import SessionLocal
from app.repositories import SyncDispatchOutboxRepository

logger = logging.getLogger(__name__)

_TASK_BY_SYNC_TYPE = {
    "full_import": "app.tasks.sync.run_full_import",
    "incremental_sync": "app.tasks.sync.run_incremental_sync",
}


class SyncDispatchDispatcher:
    """Publishes durable sync commands and leaves failures eligible for retry."""

    def __init__(self, *, repository, queue_client) -> None:
        self.repository = repository
        self.queue_client = queue_client

    def dispatch_pending(self, *, limit: int = 50) -> int:
        dispatched_count = 0
        for dispatch in self.repository.claim_pending(limit=limit):
            try:
                task_name = _TASK_BY_SYNC_TYPE[dispatch.sync_type]
                self.queue_client.send_task(task_name, kwargs=dispatch.payload_json)
            except Exception as exc:
                self.repository.reschedule_after_publish_failure(
                    dispatch, error_message=str(exc)
                )
                logger.warning(
                    "Failed to publish durable sync dispatch; it will be retried.",
                    extra={
                        "sync_dispatch.id": dispatch.id,
                        "sync_job.id": dispatch.sync_job_id,
                        "user.id": dispatch.user_id,
                    },
                )
                continue
            self.repository.mark_dispatched(dispatch)
            dispatched_count += 1
            logger.info(
                "Published durable sync dispatch.",
                extra={
                    "sync_dispatch.id": dispatch.id,
                    "sync_job.id": dispatch.sync_job_id,
                    "user.id": dispatch.user_id,
                },
            )
        return dispatched_count


def dispatch_pending_syncs() -> int:
    session = SessionLocal()
    try:
        dispatcher = SyncDispatchDispatcher(
            repository=SyncDispatchOutboxRepository(session), queue_client=celery_app
        )
        return dispatcher.dispatch_pending()
    finally:
        session.close()
