import time
from app.config import settings
from app.logging import JobLogContext, configure_logging, reset_log_job, set_log_job
from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging, task_failure, task_postrun, task_prerun

import logging

celery_app = Celery(
    "garmin_insights_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.sync", "app.tasks.coaching"],
)
celery_app.conf.beat_schedule = {
    "schedule-daily-incremental-syncs": {
        "task": "app.tasks.sync.schedule_daily_incremental_syncs",
        "schedule": crontab(
            minute=settings.daily_sync_cron_minute_utc,
            hour=settings.daily_sync_cron_hour_utc,
        ),
    },
    "generate-ai-coaching": {
        "task": "app.tasks.coaching.generate_coaching",
        "schedule": crontab(minute=f"*/{settings.coaching_poll_interval_minutes}"),
    },
}
celery_app.conf.timezone = "UTC"
celery_app.conf.worker_hijack_root_logger = False

logger = logging.getLogger(__name__)
_task_started_at: dict[str, float] = {}
_task_log_tokens = {}


@celery_app.task
def ping() -> str:
    return "pong"


@setup_logging.connect
def configure_celery_logging(*_args, **_kwargs) -> None:
    configure_logging(
        log_level=settings.log_level,
        service_name=settings.service_name,
    )
    logger.info("Configured Celery logging.")


@task_prerun.connect
def log_task_start(task_id=None, task=None, args=None, kwargs=None, **_ignored) -> None:
    if task_id is None or task is None:
        return
    _task_started_at[task_id] = time.perf_counter()
    values = kwargs or {}
    _task_log_tokens[task_id] = set_log_job(
        JobLogContext(
            task_id, task.name, values.get("user_id"), values.get("sync_job_id")
        )
    )
    logger.info(
        "Task started.",
        extra={
            "task.id": task_id,
            "task.name": task.name,
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
            **(
                {
                    key: value
                    for key, value in retval.items()
                    if key
                       in {
                           "activity_notes_generated",
                           "period_summaries_generated",
                           "training_plans_generated",
                           "failures",
                           "rate_limited",
                           "skipped_reason",
                       }
                }
                if isinstance(retval, dict)
                else {}
            ),
        },
    )
    token = _task_log_tokens.pop(task_id, None)
    if token is not None:
        reset_log_job(token)


@task_failure.connect
def log_task_failure(task_id=None, exception=None, traceback=None, sender=None, kwargs=None, **_ignored) -> None:
    started_at = None if task_id is None else _task_started_at.get(task_id)
    duration_ms = None if started_at is None else round((time.perf_counter() - started_at) * 1000, 2)
    logger.error(
        "Task failed.",
        exc_info=(type(exception), exception, traceback) if exception is not None else None,
        extra={
            "task.id": task_id,
            "task.name": None if sender is None else sender.name,
            "duration_ms": duration_ms,
        },
    )
