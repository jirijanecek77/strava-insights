import logging
import time

from celery import Celery
from celery.signals import setup_logging, task_failure, task_postrun, task_prerun
from celery.schedules import crontab

from app.config import settings
from app.logging import configure_logging


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
celery_app.conf.worker_hijack_root_logger = False

logger = logging.getLogger(__name__)
_task_started_at: dict[str, float] = {}


@celery_app.task
def ping() -> str:
    return "pong"


@setup_logging.connect
def configure_celery_logging(*_args, **_kwargs) -> None:
    configure_logging(
        log_level=settings.log_level,
    )
    logger.info("Configured Celery logging.")


@task_prerun.connect
def log_task_start(task_id=None, task=None, args=None, kwargs=None, **_ignored) -> None:
    if task_id is None or task is None:
        return
    _task_started_at[task_id] = time.perf_counter()
    logger.info(
        "Task started.",
        extra={
            "task.id": task_id,
            "task.name": task.name,
            "task.kwargs": kwargs or {},
        },
    )


@task_postrun.connect
def log_task_complete(task_id=None, task=None, state=None, retval=None, **_ignored) -> None:
    if task_id is None or task is None:
        return
    started_at = _task_started_at.pop(task_id, None)
    duration_ms = None if started_at is None else round((time.perf_counter() - started_at) * 1000, 2)
    logger.info(
        "Task completed.",
        extra={
            "task.id": task_id,
            "task.name": task.name,
            "task.state": state,
            "duration_ms": duration_ms,
        },
    )


@task_failure.connect
def log_task_failure(task_id=None, exception=None, traceback=None, sender=None, kwargs=None, **_ignored) -> None:
    started_at = None if task_id is None else _task_started_at.pop(task_id, None)
    duration_ms = None if started_at is None else round((time.perf_counter() - started_at) * 1000, 2)
    logger.error(
        "Task failed.",
        exc_info=(type(exception), exception, traceback) if exception is not None else None,
        extra={
            "task.id": task_id,
            "task.name": None if sender is None else sender.name,
            "task.kwargs": kwargs or {},
            "duration_ms": duration_ms,
        },
    )
