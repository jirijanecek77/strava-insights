from celery import Celery

from app.core.config import settings


celery_app = Celery(
    "strava_insights_backend",
    broker=settings.redis_url,
    backend=settings.redis_url,
)


class CeleryQueueClient:
    def enqueue_full_import(self, *, sync_job_id: int, user_id: int) -> None:
        celery_app.send_task(
            "app.tasks.sync.run_full_import",
            kwargs={"sync_job_id": sync_job_id, "user_id": user_id},
        )

    def enqueue_incremental_sync(self, *, sync_job_id: int, user_id: int) -> None:
        celery_app.send_task(
            "app.tasks.sync.run_incremental_sync",
            kwargs={"sync_job_id": sync_job_id, "user_id": user_id},
        )
