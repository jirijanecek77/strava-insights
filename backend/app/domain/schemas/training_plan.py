from datetime import date, datetime
from pydantic import BaseModel
from typing import Literal


class TrainingPlanItem(BaseModel):
    planned_date: date
    kind: Literal["run", "rest"]
    focus: str
    distance_km: float | None
    pace_seconds_per_km: int | None
    heart_rate_bpm: int | None
    rationale: str
    generated_at: datetime
    request_id: int
    stale: bool
    has_completed_activity: bool


class WeeklyTrainingObjective(BaseModel):
    mode: Literal["build", "maintain", "recover"]
    block_start: date
    review_date: date
    reason: str
    evidence: list[str]
    continued: bool
    target_distance_km: float
    distance_min_km: float
    distance_max_km: float
    target_running_days: int
    long_run_min_km: float
    long_run_max_km: float


class TrainingPlanResponse(BaseModel):
    items: list[TrainingPlanItem]
    status: str
    timezone: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    generated_at: datetime | None = None
    message: str | None = None
    weekly_objective: WeeklyTrainingObjective | None = None
