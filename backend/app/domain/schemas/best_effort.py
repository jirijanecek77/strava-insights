from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BestEffortItem(BaseModel):
    effort_code: str
    best_time_seconds: int
    distance_meters: Decimal
    activity_id: int | None = None
    achieved_at: datetime | None = None


class BestEffortsResponse(BaseModel):
    items: list[BestEffortItem]
