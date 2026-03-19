from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class PeriodSummarySchema(BaseModel):
    sport_type: str
    period_type: str
    period_start: date
    activity_count: int
    total_distance_meters: Decimal
    total_moving_time_seconds: int
    average_speed_mps: Decimal | None = None
    average_pace_seconds_per_km: Decimal | None = None
    average_heart_rate_drift_bpm: Decimal | None = None
    total_elevation_gain_meters: Decimal | None = None


class PeriodComparisonSchema(BaseModel):
    current: PeriodSummarySchema | None = None
    previous: PeriodSummarySchema | None = None
    delta_distance_meters: Decimal | None = None
    delta_moving_time_seconds: int | None = None
    delta_activity_count: int | None = None
    delta_average_speed_mps: Decimal | None = None
    delta_average_pace_seconds_per_km: Decimal | None = None


class DashboardResponse(BaseModel):
    month: list[PeriodComparisonSchema]
    year: list[PeriodComparisonSchema]


class TrendsResponse(BaseModel):
    period_type: str
    items: list[PeriodSummarySchema]
