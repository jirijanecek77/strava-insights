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
    heart_rate_drift_bpm: Decimal | None = None


class ActivityListResponse(BaseModel):
    items: list[ActivityListRow]


class ActivityKpis(BaseModel):
    distance_km: Decimal | None = None
    moving_time_display: str | None = None
    summary_metric_display: str | None = None
    summary_metric_kind: str | None = None
    total_elevation_gain_meters: Decimal | None = None
    average_heartrate_bpm: Decimal | None = None
    heart_rate_drift_bpm: Decimal | None = None


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


class RunningBandSummary(BaseModel):
    code: str
    label: str
    distance_km: float
    share_percent: float


class RunningAgreementSummary(BaseModel):
    matching_distance_km: float
    matching_share_percent: float
    pace_higher_distance_km: float
    pace_higher_share_percent: float
    heart_rate_higher_distance_km: float
    heart_rate_higher_share_percent: float


class RunningBlockSummary(BaseModel):
    start_distance_km: float
    end_distance_km: float
    distance_km: float


class RunningAnalysisResponse(BaseModel):
    pace_distribution: list[RunningBandSummary]
    heart_rate_distribution: list[RunningBandSummary]
    agreement: RunningAgreementSummary
    steady_threshold_block: RunningBlockSummary
    above_threshold_block: RunningBlockSummary
    interpretation: str
    activity_evaluation: str
    further_training_suggestion: str


class ActivityDetailThresholds(BaseModel):
    aet_heart_rate_bpm: float
    ant_heart_rate_bpm: float
    aet_pace_min_per_km: float
    ant_pace_min_per_km: float


class ActivityDetailResponse(BaseModel):
    id: int
    sport_type: str
    name: str
    description: str | None = None
    start_date_local: datetime | None = None
    kpis: ActivityKpis
    map: ActivityMap | None = None
    series: ActivitySeries
    thresholds: ActivityDetailThresholds | None = None
    running_analysis: RunningAnalysisResponse | None = None
