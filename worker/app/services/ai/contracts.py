"""Detached application values. Framework messages and ORM rows stay at the edges."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Protocol

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.services.coaching.contracts import (
    ActivityFacts,
    EffortCandidates,
    HeartRateCoverage,
    HierarchyFacts,
    ThresholdSnapshot,
)


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Operation(StrEnum):
    ACTIVITY = "activity"
    WEEK = "week"
    MONTH = "month"
    PLAN = "plan"


class ActivityMetrics(Value):
    date: date
    sport: str
    name: str
    distance_km: float = Field(ge=0)
    moving_time: str
    elapsed_time: str | None = None
    elevation_gain_m: float | None = None
    avg_hr_bpm: float | None = None
    avg_pace: str | None = None
    avg_speed_kph: float | None = None
    average_cadence: float | None = None
    athlete_notes: str | None = None


class Interpretation(Value):
    date: date
    sport: str
    summary: str | None
    activity_id: int | None = None


class SportTotals(Value):
    activities: int = Field(ge=0)
    distance_km: float = Field(ge=0)
    moving_seconds: float = Field(ge=0)


class RecentTraining(Value):
    previous_activities: list[Interpretation]
    days_since_previous_activity: int | None = None
    totals_last_7_days_by_sport: dict[str, SportTotals] = Field(default_factory=dict)


class RecordedLap(Value):
    split: int
    type: str | None = None
    distance_km: float
    duration_seconds: float | None = None
    avg_hr_bpm: float | None = None
    pace: str | None = None
    speed_kph: float | None = None
    terrain: dict[str, JsonValue] | None = None


class CandidateEvidence(Value):
    candidates: EffortCandidates


class ActivityContext(Value):
    activity: ActivityMetrics
    activity_evidence: CandidateEvidence
    terrain_context: dict[str, JsonValue]
    athlete_thresholds: dict[str, float | str] | None = None
    splits: list[RecordedLap] = Field(default_factory=list)
    heart_rate_zones: dict[str, float] | None = None
    recent_training: RecentTraining | None = None
    best_efforts: list[dict[str, JsonValue]] = Field(default_factory=list)
    route_comparison: dict[str, JsonValue] | None = None
    split_data_limitation: str | None = None


class ComparisonWindow(Value):
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
    current_days: int
    previous_days: int


class DateCoverage(Value):
    covered_days: int
    period_days: int
    previous_covered_days: int
    previous_period_days: int


class PeriodBand(Value):
    time_s: float | None
    distance_m: float | None
    time_percent: float | None


class PeriodBands(Value):
    below_aet: PeriodBand
    between_aet_ant: PeriodBand
    above_ant: PeriodBand


class SportHrEvidence(Value):
    activities: int
    activities_missing_hr: int
    bands: PeriodBands
    coverage: HeartRateCoverage
    limitations: list[str]
    threshold_definitions: list[ThresholdSnapshot]


class DistanceComparison(Value):
    current_distance_m: float
    previous_distance_m: float
    change_m: float
    change_pct: float | None


class PeriodContextData(Value):
    period_type: Literal["week", "month"]
    period_start: date
    period_end: date
    in_progress: bool
    comparison_windows: ComparisonWindow
    date_coverage: DateCoverage
    totals_by_sport: dict[str, SportTotals]
    previous_period_totals_by_sport: dict[str, SportTotals]
    previous_full_period_totals_by_sport: dict[str, SportTotals]
    # Sport/band/comparison dimensions are dynamic persisted JSON boundaries.
    hr_bands_by_sport: dict[str, SportHrEvidence]
    previous_hr_bands_by_sport: dict[str, SportHrEvidence]
    distance_comparison_by_sport: dict[str, DistanceComparison]
    hr_band_distance_comparison_by_sport: dict[str, JsonValue]
    performance_comparison: dict[str, JsonValue]
    interpretation_coverage: dict[str, int]
    training_days: int
    running_days: int
    rest_days: int | None
    previous_reviews: list[dict[str, JsonValue]]
    limitations: list[str]
    activities: list[Interpretation] | None = None
    weeks: list[dict[str, JsonValue]] | None = None


class CompletedTraining(Value):
    date: date
    sport: Literal["Run", "Ride", "EBikeRide"]
    distance_km: float = Field(ge=0)
    moving_minutes: float = Field(ge=0)
    elevation_gain_meters: float | None
    pace_seconds_per_km: float | None
    hr_bpm: float | None
    coaching_summary: str | None
    coaching_status: Literal["ready", "pending", "generating", "failed", "unavailable"]


class Thresholds(Value):
    aet_heart_rate_bpm: float | None
    ant_heart_rate_bpm: float | None
    aet_pace_min_per_km: float | None
    ant_pace_min_per_km: float | None


class AerobicResponse(Value):
    compared_days: int
    adverse_dates: list[date]
    evidence: list[str]


class WeeklyObjective(Value):
    mode: Literal["build", "maintain", "recover"]
    block_start: date
    review_date: date
    decision_date: date
    continued: bool
    reason: str
    evidence: list[str]
    current_response: AerobicResponse
    distance_min_km: float
    distance_max_km: float
    target_running_days: int
    long_run_min_km: float
    long_run_max_km: float
    target_distance_km: float


class TrainingBounds(Value):
    weekly_distances_km: list[float]
    weekly_running_days: list[int]
    weekly_long_distances_km: list[float]
    typical_weekly_distance_km: float
    recent_all_sport_minutes: list[float]
    recovery_load_spike: bool
    max_weekly_distance_km: float
    max_run_distance_km: float
    max_running_days: int
    max_quality_days: int
    min_easy_pace_seconds_per_km: int
    min_easy_distance_share: float
    min_pace_seconds_per_km: int
    max_pace_seconds_per_km: int
    easy_hr_ceiling_bpm: float
    max_hr_bpm: float
    recent_hard_dates: list[date]
    recent_long_dates: list[date]
    min_weekly_distance_km: float
    min_running_days: int
    min_long_run_distance_km: float
    min_quality_days: int


class PlanningContext(Value):
    today: date
    dates: list[date] = Field(min_length=7, max_length=7)
    timezone: str
    thresholds: Thresholds
    activities: list[CompletedTraining]
    policy_version: str
    bounds: TrainingBounds
    weekly_objective: WeeklyObjective

    @model_validator(mode="after")
    def consecutive_dates(self):
        from datetime import timedelta

        if self.dates != [self.today + timedelta(days=i) for i in range(1, 8)]:
            raise ValueError(
                "Forecast must cover the seven dates after its decision date"
            )
        return self


Text = Annotated[str, Field(min_length=1)]


class ModelResult(Value):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        allow_inf_nan=False,
        str_strip_whitespace=True,
    )


class ActivityResult(ModelResult):
    description: Text = Field(
        description="Interpret execution and expected stimulus from supplied evidence. Do not repeat displayed KPIs. Low HR, zero drift or terrain alone cannot establish adequate recovery or absence of fatigue; qualify uncertainty."
    )
    summary: Text = Field(
        description="At most 40 words. Preserve relevant terrain and missing-data qualifications; distinguish expected stimulus from demonstrated improvement."
    )
    recommendation: Text = Field(
        description="Useful next-session guidance grounded in supplied load and thresholds. Do not invent a required weekly kilometre target, numerical progression or session cap without supplied capacity bounds."
    )

    @field_validator("summary")
    @classmethod
    def concise_summary(cls, value):
        if len(value.split()) > 40:
            raise ValueError("Activity summary exceeds 40 words")
        return value


class PeriodResult(ModelResult):
    summary: Text = Field(
        description="Qualify incomplete evidence and comparable-effort counts. Missing saved weeks are unknown coverage, not rest. Boundary-week prose is context; only clipped numerical facts support this period's totals and findings."
    )
    recommendation: Text = Field(
        description="Useful next-period advice consistent with known load, limitations and recovery evidence, without invented measured improvement or thresholds."
    )


class PlanDay(ModelResult):
    date: str
    kind: Literal["run", "rest"]
    focus: Literal["easy", "long", "threshold", "speed", "recovery", "rest"]
    distance_km: float | None
    pace_seconds_per_km: int | None
    heart_rate_bpm: int | None
    rationale: Annotated[str, Field(min_length=1, max_length=240)]

    @field_validator("date")
    @classmethod
    def calendar_date(cls, value):
        date.fromisoformat(value)
        return value


class PlanResult(ModelResult):
    days: list[PlanDay] = Field(min_length=7, max_length=7)


Result = ActivityResult | PeriodResult | PlanResult
Context = ActivityContext | PeriodContextData | PlanningContext


class ProviderUsage(Value):
    integration_version: str | None = None
    schema_fingerprint: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    request_id: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    error_type: str | None = None
    latency_ms: float = 0


@dataclass(frozen=True, slots=True)
class WorkClaim:
    operation: Operation
    id: int
    user_id: int
    token: str
    attempt_count: int
    activity_id: int | None = None
    period_start: date | None = None
    timezone: str = "Europe/Prague"
    saved_context: PlanningContext | None = None
    last_error: str | None = None


@dataclass(frozen=True, slots=True)
class InputSnapshot:
    claim: WorkClaim
    context: Context
    revision: str
    prompt_fingerprint: str
    system_prompt: str
    user_prompt: str
    prompt_version: str
    prepared_on: date
    handoff: ActivityFacts | HierarchyFacts | None = None
    metrics: dict[str, JsonValue] | None = None
    source_hash: str | None = None
    is_final: bool = False

    @property
    def completion_limit(self) -> int:
        return 4096 if self.claim.operation == Operation.PLAN else 2048


@dataclass(frozen=True, slots=True)
class GeneratedResult:
    value: Result
    model: str
    usage: ProviderUsage
    attempt_id: str | None = None


class DeferredInputs(Exception):
    """Required local/child work is not ready; no provider request may start."""


class RejectedPlan(Exception):
    """Safe feedback produced only by deterministic training-rule validation."""


class ObsoleteWork(Exception):
    """The detached owner or input snapshot is no longer eligible."""


class AttemptRecorder(Protocol):
    def begin(
        self,
        snapshot: InputSnapshot,
        *,
        model: str,
        metadata: ProviderUsage | None = None
    ) -> str: ...
    def finish(
        self, attempt_id: str, *, outcome: str, usage: ProviderUsage
    ) -> None: ...


class ModelProvider(Protocol):
    is_configured: bool
    model: str

    def generate(self, snapshot: InputSnapshot) -> GeneratedResult: ...
