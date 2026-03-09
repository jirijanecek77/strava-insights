from celery import Celery
from celery.schedules import crontab

from app.config import settings


celery_app = Celery(
    "strava_insights_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.sync"],
)
celery_app.conf.beat_schedule = {
    "schedule-daily-incremental-syncs": {
        "task": "app.tasks.sync.schedule_daily_incremental_syncs",
        "schedule": crontab(
            minute=settings.daily_sync_cron_minute_utc,
            hour=settings.daily_sync_cron_hour_utc,
        ),
    }
}
celery_app.conf.timezone = "UTC"


@celery_app.task
def ping() -> str:
    return "pong"
