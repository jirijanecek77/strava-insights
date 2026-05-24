import logging
from contextvars import ContextVar, Token
from logging.config import dictConfig


_log_user_name: ContextVar[str] = ContextVar("log_user_name", default="-")


class LogContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.user_name = _log_user_name.get()
        return True


def set_log_user_name(user_name: str | None) -> Token[str]:
    normalized_user_name = (user_name or "").strip() or "-"
    return _log_user_name.set(normalized_user_name)


def reset_log_user_name(token: Token[str]) -> None:
    _log_user_name.reset(token)


def configure_logging(
    *,
    log_level: str,
) -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s [worker] [user=%(user_name)s] [%(name)s] %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S%z",
                }
            },
            "filters": {
                "context": {
                    "()": LogContextFilter,
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
