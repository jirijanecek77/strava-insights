import json
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from logging.config import dictConfig

import logging

_log_user_name: ContextVar[str] = ContextVar("log_user_name", default="-")


@dataclass(frozen=True, slots=True)
class JobLogContext:
    task_id: str | None = None
    task_name: str | None = None
    user_id: int | None = None
    sync_job_id: int | None = None
    activity_id: int | None = None
    planning_request_id: int | None = None


_log_job: ContextVar[JobLogContext | None] = ContextVar("log_job", default=None)


def set_log_job(context: JobLogContext) -> Token:
    return _log_job.set(context)


def reset_log_job(token: Token) -> None:
    _log_job.reset(token)


@contextmanager
def log_work_item(
        *,
        user_id: int,
        activity_id: int | None = None,
        planning_request_id: int | None = None,
):
    token = set_log_job(
        replace(
            _log_job.get() or JobLogContext(),
            user_id=user_id,
            activity_id=activity_id,
            planning_request_id=planning_request_id,
        )
    )
    try:
        yield
    finally:
        reset_log_job(token)


class WorkerLogFormatter(logging.Formatter):
    """Render operational metadata, without dumping task arguments or provider payloads."""

    _fields = frozenset(
        {
            "task.id",
            "task.name",
            "task.state",
            "user.id",
            "activity.id",
            "activity.source_id",
            "sync_job.id",
            "sync_dispatch.id",
            "duration_ms",
            "retry_after_seconds",
            "after",
            "checkpoint",
            "deleted_keys",
            "derived_data_changed",
            "routes_updated",
            "scheduled_jobs",
            "stage",
            "error.class",
            "skipped_reason",
            "rate_limited",
            "activity_notes_generated",
            "period_summaries_generated",
            "training_plans_generated",
            "failures",
            "llm.model",
            "llm.prompt_tokens",
            "llm.completion_tokens",
            "llm.total_tokens",
            "llm.request_id",
            "llm.status_code",
            "llm.error_code",
            "llm.error_type",
            "llm.finish_reason",
            "llm.input_characters",
            "llm.max_completion_tokens",
            "ai.operation", "ai.work_id", "ai.attempt_id", "ai.input_revision",
            "ai.prompt_version", "ai.outcome", "ai.provider_calls", "ai.work_items", "ai.obsolete",
        }
    )
    _prefixes = ("coaching.", "planning.", "derived.", "progress.", "route.")

    def format(self, record: logging.LogRecord) -> str:
        values = {
            key: value
            for key, value in record.__dict__.items()
            if (
                       key in self._fields
                       or key.startswith(self._prefixes)
                       or (key.endswith("_count") and isinstance(value, int))
               )
               and value is not None
               and isinstance(value, (str, int, float, bool))
        }
        result = super().format(record)
        return result + (
            " "
            + json.dumps(
                values, ensure_ascii=True, separators=(",", ":"), sort_keys=True
            )
            if values
            else ""
        )


class LogContextFilter(logging.Filter):

    def __init__(self, service_name: str = "worker"):
        super().__init__()
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.user_name = _log_user_name.get()
        record.service_name = self.service_name
        job = _log_job.get()
        if job:
            for key, value in {
                "task.id": job.task_id,
                "task.name": job.task_name,
                "user.id": job.user_id,
                "sync_job.id": job.sync_job_id,
                "activity.id": job.activity_id,
                "planning.request_id": job.planning_request_id,
            }.items():
                record.__dict__.setdefault(key, value)
        return True


def set_log_user_name(user_name: str | None) -> Token[str]:
    normalized_user_name = (user_name or "").strip() or "-"
    return _log_user_name.set(normalized_user_name)


def reset_log_user_name(token: Token[str]) -> None:
    _log_user_name.reset(token)


def configure_logging(
    *,
    log_level: str,
        service_name: str = "worker",
) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "()": WorkerLogFormatter,
                    "format": "%(asctime)s %(levelname)s [%(service_name)s] [user=%(user_name)s] [%(name)s] %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S%z",
                }
            },
            "filters": {
                "context": {
                    "()": LogContextFilter,
                    "service_name": service_name,
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "filters": ["context"],
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "app": {
                    "handlers": ["default"],
                    "level": log_level.upper(),
                    "propagate": False,
                }
            },
            "root": {
                "level": log_level.upper(),
                "handlers": ["default"],
            },
        }
    )

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery.redirected").setLevel(logging.WARNING)
