"""Persisted, compact handoffs between the three coaching levels.

These models contain calculated facts, never streams or recorded lap arrays.
Pydantic validates the JSON boundary; ordinary dictionaries are serialization only.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CoachingValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class BandValues(CoachingValue):
    time_s: float | None = Field(default=None, ge=0)
    distance_m: float | None = Field(default=None, ge=0)


class HeartRateBands(CoachingValue):
    below_aet: BandValues = Field(default_factory=BandValues)
    between_aet_ant: BandValues = Field(default_factory=BandValues)
    above_ant: BandValues = Field(default_factory=BandValues)


class HeartRateCoverage(CoachingValue):
    classified_time_s: float = Field(default=0, ge=0)
    classified_distance_m: float = Field(default=0, ge=0)
    unknown_time_s: float = Field(default=0, ge=0)
    unknown_distance_m: float = Field(default=0, ge=0)


class HeartRateEvidence(CoachingValue):
    bands: HeartRateBands = Field(default_factory=HeartRateBands)
    coverage: HeartRateCoverage = Field(default_factory=HeartRateCoverage)
    limitations: list[str] = Field(default_factory=list)


class Volume(CoachingValue):
    distance_m: float = Field(default=0, ge=0)
    moving_time_s: float = Field(default=0, ge=0)


class ThresholdSnapshot(CoachingValue):
    aet_hr_bpm: float
    ant_hr_bpm: float
    effective_from: str = "unknown"


class SustainedEffort(CoachingValue):
    lap_range: list[int]
    start_distance_m: float | None = None
    end_distance_m: float | None = None
    duration_s: float = Field(gt=0)
    distance_m: float = Field(gt=0)
    pace_s_per_km: float = Field(gt=0)
    hr_bpm: float = Field(gt=0)
    efficiency_m_per_beat: float | None = None
    decoupling_pct: float | None = None
    net_grade_pct: float | None = None
    ascent_m_per_km: float | None = None
    limitations: list[str] = Field(default_factory=list)


class EffortCandidates(CoachingValue):
    endurance: list[SustainedEffort] = Field(default_factory=list, max_length=3)
    tempo: list[SustainedEffort] = Field(default_factory=list, max_length=3)


class ActivityFacts(CoachingValue):
    activity_id: int
    date: date
    sport: str
    route_group_id: int | None = None
    threshold_snapshot: ThresholdSnapshot | None = None
    volume: Volume
    hr_bands: HeartRateEvidence
    candidates: EffortCandidates = Field(default_factory=EffortCandidates)


class ActivityEvaluation(CoachingValue):
    facts: ActivityFacts
    summary: str | None = None
    revision: str
    status: str
    facts_ready: bool = True


class DailyFacts(CoachingValue):
    date: date
    activities: list[ActivityFacts] = Field(default_factory=list)
    input_revisions: dict[str, str] = Field(default_factory=dict)


class HierarchyFacts(CoachingValue):
    version: Literal[1] = 1
    as_of: date
    days: list[DailyFacts] = Field(default_factory=list)
    input_revisions: dict[str, str] = Field(default_factory=dict)


class PeriodEvaluation(CoachingValue):
    model_config = ConfigDict(from_attributes=True, allow_inf_nan=False)

    period_type: Literal["week", "month"]
    period_start: date
    status: str
    summary: str | None = None
    recommendation: str | None = None
    source_hash: str | None = None
    metrics: dict | None = None
    is_final: bool = False
