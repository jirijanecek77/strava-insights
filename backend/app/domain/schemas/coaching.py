from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

CoachingStatus = Literal["pending", "generating", "ready", "failed"]


class ActivityCoachingResponse(BaseModel):
    status: CoachingStatus
    description: str | None = None
    summary: str | None = None
    recommendation: str | None = None
    model: str | None = None
    generated_at: datetime | None = None


class PeriodCoachingItem(BaseModel):
    period_type: Literal["week", "month"]
    period_start: date
    period_end: date
    status: CoachingStatus
    summary: str | None = None
    recommendation: str | None = None
    is_final: bool = False
    model: str | None = None
    generated_at: datetime | None = None


class PeriodCoachingResponse(BaseModel):
    items: list[PeriodCoachingItem]
