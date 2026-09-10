import time
from app.config import settings
from app.logging import configure_logging
from app.services.sync_dispatcher import dispatch_pending_syncs

import logging

logger = logging.getLogger(__name__)


def main() -> None:
    configure_logging(log_level=settings.log_level)
    logger.info("Starting durable sync-dispatch outbox runner.")
    while True:
        try:
            dispatch_pending_syncs()
        except Exception:
            logger.exception("Durable sync-dispatch outbox runner failed.")
        time.sleep(settings.sync_dispatch_poll_interval_seconds)


if __name__ == "__main__":
    main()
