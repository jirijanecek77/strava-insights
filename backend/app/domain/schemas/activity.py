from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ActivityListRow(BaseModel):
    id: int
    sport_type: str
    name: str
    start_date_local: datetime | None = None
    distance_km: Decimal | None = None
    moving_time_display: str | None = None
    summary_metric_display: str | None = None
    summary_metric_kind: str | None = None
    total_elevation_gain_meters: Decimal | None = None
    average_heartrate_bpm: Decimal | None = None
    difficulty_score: Decimal | None = None


class ActivityListResponse(BaseModel):
    items: list[ActivityListRow]


class ActivityKpis(BaseModel):
    distance_km: Decimal | None = None
    moving_time_display: str | None = None
    summary_metric_display: str | None = None
    summary_metric_kind: str | None = None
    total_elevation_gain_meters: Decimal | None = None
    average_heartrate_bpm: Decimal | None = None
    difficulty_score: Decimal | None = None


class ActivitySeries(BaseModel):
    distance_km: list[float]
    altitude_meters: list[float]
    moving_average_heartrate: list[float]
    moving_average_speed_kph: list[float]
    pace_minutes_per_km: list[float]
    pace_display: list[str]
    slope_percent: list[float]


class ActivityMap(BaseModel):
    polyline: list[list[float]]
    bounds: dict[str, float] | None = None


class ActivityDetailResponse(BaseModel):
    id: int
    sport_type: str
    name: str
    description: str | None = None
    start_date_local: datetime | None = None
    kpis: ActivityKpis
    map: ActivityMap | None = None
    series: ActivitySeries
    intervals: list[dict]
    zone_summary: dict
    compliance: dict | None = None
    zones: list[dict]
