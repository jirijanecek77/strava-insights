"""Optional recorded-lap fetch using the activity import's existing Garmin session."""

import logging

from app.garmin_client import GarminAuthenticationError

logger = logging.getLogger(__name__)


def fetch_recorded_splits(garmin_client, garmin_session, source_activity_id: int) -> list[dict]:
    try:
        return garmin_client.get_activity_splits(garmin_session, source_activity_id)
    except GarminAuthenticationError:
        raise
    except Exception:
        # Splits are optional; leave reconnect handling to the normal import flow.
        # Never log provider response bodies or credentials.
        logger.warning("Recorded splits unavailable during activity import.",
                       extra={"activity.source_id": source_activity_id})
        return []
