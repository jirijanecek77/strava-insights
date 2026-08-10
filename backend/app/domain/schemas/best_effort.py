from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BestEffortItem(BaseModel):
    sport_type: str
    effort_code: str
    best_time_seconds: int
    distance_meters: Decimal
    activity_id: int | None = None
    achieved_at: datetime | None = None
    rank: int
    pace_seconds_per_km: float | None = None
    average_speed_kph: float | None = None


class BestEffortsResponse(BaseModel):
    items: list[BestEffortItem]
