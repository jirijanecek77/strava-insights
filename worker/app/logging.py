import logging
from logging.config import dictConfig


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
                    "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
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
