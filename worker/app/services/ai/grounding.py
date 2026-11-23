"""Interpretation limits derived from the existing authoritative numerical facts."""

import json
from dataclasses import asdict, dataclass, replace

from app.services.ai.contracts import (
    ActivityContext,
    InputSnapshot,
    Operation,
    PeriodContextData,
)
from app.services.coaching.evidence import fingerprint


@dataclass(frozen=True)
class DecouplingBlock:
    first_lap: int
    last_lap: int
    decoupling_percent: float


@dataclass(frozen=True)
class InterpretationLimits:
    heart_rate_available: bool
    contains_recovery_laps: bool
    valid_steady_block_decoupling: tuple[DecouplingBlock, ...]
    fatigue_or_recovery_state_measured: bool = False


def activity_limits(context: ActivityContext) -> InterpretationLimits:
    return InterpretationLimits(
        heart_rate_available=context.heart_rate_zones is not None,
        contains_recovery_laps=any(
            (lap.type or "").upper() in {"RECOVERY", "REST"} for lap in context.splits
        ),
        valid_steady_block_decoupling=tuple(
            DecouplingBlock(
                block.lap_range[0], block.lap_range[-1], block.decoupling_pct
            )
            for block in context.activity_evidence.candidates.endurance
            if block.decoupling_pct is not None
        ),
    )


def grounded_snapshot(snapshot: InputSnapshot) -> InputSnapshot:
    if snapshot.claim.operation in {Operation.WEEK, Operation.MONTH}:
        return grounded_period(snapshot)
    if snapshot.claim.operation != Operation.ACTIVITY:
        return snapshot
    if not isinstance(snapshot.context, ActivityContext):
        raise ValueError("Activity generation requires typed activity facts")
    limits = activity_limits(snapshot.context)
    guidance = """Application interpretation limits (these constrain every description and summary):
Fatigue, readiness and recovery state were not measured. Never conclude fatigue is absent, limited, modest or moderate, or recovery adequate, from low HR, terrain, a stable pace, a lack of drift or recent volume. Say fatigue/recovery cannot be determined from these data; recommend sensible recovery without asserting a measured state.
Only the listed valid_steady_block_decoupling values support a drift statement, and only about their named lap block. An empty list means no valid drift assessment: do not claim stable/no/low drift. Recorded interval/recovery averages cannot establish whole-session drift or its absence.
Pace and HR thresholds are separate. A pace equal to AeT pace does not mean HR equals AeT HR; do not describe an HR below the threshold as matching it. Missing HR makes HR intensity and drift unknown; missing terrain means unknown grade, not proof about fatigue. Preserve the uphill explanation when present.
Workout stimulus describes expected benefit, not a demonstrated improvement. Recommendations must remain conditional on the athlete feeling recovered: never guarantee that adding intensity tomorrow is safe from a short activity history, low HR or stable decoupling. Do not call cumulative load moderate without known capacity; account for recent intensity and favor recovery before further quality work when readiness is unknown.
Use real paragraph breaks, not literal backslash-n text. Interpret rather than restating the displayed measurements.
Locally calculated limits: """ + json.dumps(
        asdict(limits), sort_keys=True, separators=(",", ":")
    )
    system = guidance + "\n\n" + snapshot.system_prompt
    return replace(
        snapshot,
        system_prompt=system,
        prompt_version=f"{snapshot.prompt_version}-g3",
        prompt_fingerprint=fingerprint([system, snapshot.user_prompt]),
    )


@dataclass(frozen=True)
class PeriodInterpretationLimits:
    distance_change_percent: dict[str, float | None]
    unknown_hr_seconds: dict[str, float]
    current_all_sport_minutes: float
    previous_all_sport_minutes: float
    current_sport_duration_hms: dict[str, str]
    previous_sport_duration_hms: dict[str, str]
    covered_dates: int
    total_dates: int
    previous_covered_dates: int
    previous_total_dates: int
    fatigue_or_recovery_state_measured: bool = False


def duration_hms(seconds: float) -> str:
    hours, remainder = divmod(round(seconds), 3600)
    minutes, seconds_part = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds_part:02d}"


def period_limits(context: PeriodContextData) -> PeriodInterpretationLimits:
    return PeriodInterpretationLimits(
        distance_change_percent={
            sport: change.change_pct
            for sport, change in context.distance_comparison_by_sport.items()
        },
        unknown_hr_seconds={
            sport: evidence.coverage.unknown_time_s
            for sport, evidence in context.hr_bands_by_sport.items()
        },
        current_all_sport_minutes=sum(
            total.moving_seconds for total in context.totals_by_sport.values()
        )
        / 60,
        previous_all_sport_minutes=sum(
            total.moving_seconds
            for total in context.previous_period_totals_by_sport.values()
        )
        / 60,
        current_sport_duration_hms={
            sport: duration_hms(total.moving_seconds)
            for sport, total in context.totals_by_sport.items()
        },
        previous_sport_duration_hms={
            sport: duration_hms(total.moving_seconds)
            for sport, total in context.previous_period_totals_by_sport.items()
        },
        covered_dates=context.date_coverage.covered_days,
        total_dates=context.date_coverage.period_days,
        previous_covered_dates=context.date_coverage.previous_covered_days,
        previous_total_dates=context.date_coverage.previous_period_days,
    )


def grounded_period(snapshot: InputSnapshot) -> InputSnapshot:
    if not isinstance(snapshot.context, PeriodContextData):
        raise ValueError("Period generation requires typed saved numerical evidence")
    limits = period_limits(snapshot.context)
    guidance = """Application interpretation limits (apply to summary and recommendation):
Focus on interpretation rather than repeating table figures. If a sport duration is essential, copy its exact locally calculated current_sport_duration_hms or previous_sport_duration_hms value (hours:minutes:seconds); never invent a different hours/minutes conversion from raw seconds. Combined all-sport minutes and per-sport durations have different scope.
Use the locally computed distance_change_percent for any volume percentage; never confuse kilometre difference with percent difference. Do not repeat table figures unnecessarily. HR-band shares describe only classified HR time. When unknown_hr_seconds is nonzero, never claim no activity reached a threshold: say no such time was recorded in the known data.
Rest days, low-HR training and stable comparison blocks do not establish adequate recovery or a measured fatigue state. Keep this unknown. Treat missing weeks as unknown training, not rest. If previous_covered_dates is less than previous_total_dates, missing previous training is unknown: zero recorded totals cannot establish a volume increase or a previous rest week. Distinguish stable comparable performance from proof of unchanged physiological capacity.
Assess combined cycling/running workload using the supplied current and previous all-sport minutes. Do not label it moderate, balanced or recovery adequate without capacity/readiness evidence; acknowledge a large increase and favor recovery/consolidation rather than automatically adding hard sessions. Missing qualified tempo comparison blocks mean no comparable tempo evidence, not that no tempo sessions or stimulus occurred in the supplied laps or cycling. Do not claim a new physiological capacity from unchanged comparison metrics.
Attribute totals and comparisons only to the exact supplied calendar windows; boundary-week narratives remain contextual. Distinguish HR thresholds, pace thresholds, counts of activities, dates and independently matched pairs.
Locally calculated limits: """ + json.dumps(
        asdict(limits), sort_keys=True, separators=(",", ":")
    )
    incomplete = limits.covered_dates < limits.total_dates
    if incomplete:
        guidance += """
Incomplete-calendar recommendation contract: uncovered dates mean unknown training, so normal weekly volume, frequency and capacity are not established. Do not prescribe a new weekly frequency, duration, distance, intensity progression, tempo session or percentage of maximum HR. Maximum HR was not supplied: never invent it or use a percentage of it. Do not tell the athlete to maintain an assumed normal weekly volume. Recommend easy activity or rest conditionally on how recovered they feel, recording future data and completing the history before a progression decision. Missing recordings are not a reason to add training or increase intensity."""
    system = snapshot.system_prompt + "\n\n" + guidance
    return replace(
        snapshot,
        system_prompt=system,
        prompt_version=(
            f"{snapshot.prompt_version}-g4-incomplete"
            if incomplete
            else f"{snapshot.prompt_version}-g3"
        ),
        prompt_fingerprint=fingerprint([system, snapshot.user_prompt]),
    )
