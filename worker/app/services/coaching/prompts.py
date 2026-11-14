"""Versioned coaching prompts and validation of the model's JSON answers."""

import json
from dataclasses import dataclass

from app.services.coaching.llm_client import LlmResponseFormatError

PROMPT_VERSION = "4"
ACTIVITY_PROMPT_VERSION = "6"

_COACH_PERSONA = (
    'You are an experienced endurance coach for running and cycling. Write in English, addressing the athlete as "you". '
    "Be specific, constructive, and grounded in supplied evidence. Running endurance and sustainable pace are the main goals; "
    "cycling is supporting cardiovascular training and recovery load. Do not invent numbers, workout intentions, conditions, "
    "feelings, or events. Use metric units. Avoid medical advice."
)

ACTIVITY_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training activity and a bounded history of up to seven previous activity evaluations and seven-day load.
Only this activity supplies detailed evidence. "splits" contains chronological recorded Garmin laps: distance, timer duration,
average pace/speed, average HR, optional lap type, Garmin-reported ascent/descent when available, and locally calculated
net change, grade and stream coverage. Garmin lap totals remain valid without an altitude stream; stream coverage
does not describe coverage of those totals. Missing Garmin totals are unavailable, not zero or locally estimated.
No stream excerpts or elevation profile are supplied. Lap averages cannot establish within-lap surges or HR response timing.
Timed recoveries remain included; timer stops are excluded. A lap label alone does not establish workout intent.
If split_data_limitation is present, qualify the analysis.

Interpret the session without repeating displayed KPIs. Explain its likely endurance and sustainable-tempo stimulus,
execution, and what evidence supports that interpretation. A useful training stimulus does not prove fitness already improved.
Anaerobic/sprint benefit cannot be read directly from time in a high HR zone; HR lags short efforts.

Use terrain to interpret pace/HR changes: an uphill finish can explain slower pace or higher HR. Total ascent cannot locate a hill.
Missing terrain is not flat terrain; terrain never proves fatigue is absent. Fatigue needs compatible independent evidence.
Only supplied eligible steady-block decoupling may inform it; never derive whole-session drift from split averages.
Comparable pace/HR evidence may indicate efficiency, with conditions and sample limitations. Cycling speed alone does not establish fitness.

Respond with a single JSON object with exactly these string fields:
- "description": three short paragraphs (80-120 words total): execution and terrain; likely endurance/tempo training stimulus;
  Fatigue/recovery evidence and comparison with recent training. State uncertainty where appropriate.
- "summary": 1-2 sentences, at most 40 words, preserving the main training benefit, execution finding, and important terrain
  explanation or limitation. This is the activity interpretation reused by the weekly coach.
- "recommendation": 2-3 concise sentences with next-session guidance supported by recent load and known thresholds.
Return only the JSON object."""

PERIOD_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training {{period_label}} as JSON. A week receives persisted activity evaluations; a month receives persisted
weekly evaluations, plus up to three earlier reviews of the same type. Dates and numeric facts are authoritative.
Do not reconstruct activities, recompute facts from prose, or invent detail lost during summarization.
The supplied HR-band percentages are weighted by time, not an average of activity percentages. Below AeT, AeT to below AnT,
and at/above AnT are the three bands. Interpret the balance; the UI already displays exact times, percentages and distances.
Avoid reciting that table. Shared configured HR thresholds also apply to cycling.

Separate likely training stimulus from demonstrated adaptation. Assess endurance and sustainable tempo independently.
Use performance_comparison for repeated comparable efforts; a faster average across different routes or higher volume alone
is not proof of improved fitness. Fewer than two independent matched pairs support only tentative observations.
Older child narratives may contain unsupported fatigue/progress claims; supplied numerical evidence and terrain limitations take precedence.
An uphill finish or interval recovery must not be relabelled as fatigue from pace alone.

Use comparison_windows for equal elapsed-calendar comparisons while in progress. A partial boundary week can contain dates outside
this calendar month: its whole narrative is context only. Attribute monthly totals and performance findings only to date-clipped
monthly facts. Prior reviews are comparison context and never part of this period's totals.
If date_coverage is incomplete, qualify totals and comparisons as available evidence. Missing weekly results are not
rest days and cannot establish reduced training, extra recovery, or declining fitness.

Respond with a single JSON object with exactly these string fields:
- "summary": {{word_range}} words interpreting training balance, endurance and tempo, recovery, and the supporting evidence.
  Explicitly distinguish improvement, maintenance, and insufficient evidence. If in_progress is true, describe the period so far.
- "recommendation": 2-3 concise sentences for the {{next_period_label}}, consistent with the evidence and current load.
Return only the JSON object."""


@dataclass(frozen=True, slots=True)
class ActivityNarrative:
    description: str
    summary: str
    recommendation: str


@dataclass(frozen=True, slots=True)
class PeriodReview:
    summary: str
    recommendation: str


def build_activity_prompt(context: dict) -> tuple[str, str]:
    return ACTIVITY_SYSTEM_PROMPT, _data_prompt("Activity data", context)


def build_period_prompt(context: dict) -> tuple[str, str]:
    is_week = context["period_type"] == "week"
    system_prompt = PERIOD_SYSTEM_PROMPT.format(
        period_label="week" if is_week else "month",
        word_range="70-100" if is_week else "90-130",
        next_period_label=(
            ("rest of the week" if is_week else "rest of the month")
            if context.get("in_progress")
            else ("next week" if is_week else "next month")
        ),
    )
    return system_prompt, _data_prompt(
        "Training period data", _period_prompt_context(context)
    )


def _period_prompt_context(context: dict) -> dict:
    """Retain useful evidence while omitting storage details and repeated numbers."""
    result = {
        key: value
        for key, value in context.items()
        if key
           not in {
               "hierarchy",
               "previous_full_period_totals_by_sport",
               "limitations",
               "hr_band_distance_comparison_by_sport",
               "distance_comparison_by_sport",
           }
    }
    for name in ("hr_bands_by_sport", "previous_hr_bands_by_sport"):
        result[name] = {
            sport: {
                "bands": row["bands"],
                "thresholds_changed": len(row.get("threshold_definitions", [])) > 1,
                "activities_missing_hr": row.get("activities_missing_hr", 0),
            }
            for sport, row in context.get(name, {}).items()
        }
    result["performance_comparison"] = {}
    for kind, comparison in context.get("performance_comparison", {}).items():
        compact = {key: value for key, value in comparison.items() if key != "evidence"}
        compact["evidence"] = [
            {
                "current_date": pair["current_date"],
                "previous_date": pair["previous_date"],
                **{
                    side: {
                        key: value
                        for key, value in pair[side].items()
                        if key
                           in {
                               "pace_s_per_km",
                               "duration_s",
                               "hr_bpm",
                               "efficiency_m_per_beat",
                               "decoupling_pct",
                           }
                    }
                    for side in ("current", "previous")
                },
            }
            for pair in comparison.get("evidence", [])
        ]
        result["performance_comparison"][kind] = compact
    return result


def parse_activity_narrative(payload: dict) -> ActivityNarrative:
    return ActivityNarrative(
        description=_required_text(payload, "description"),
        summary=_required_text(payload, "summary"),
        recommendation=_required_text(payload, "recommendation"),
    )


def parse_period_review(payload: dict) -> PeriodReview:
    return PeriodReview(
        summary=_required_text(payload, "summary"),
        recommendation=_required_text(payload, "recommendation"),
    )


def compact_context(value):
    """Round only provider payloads; reusable evidence retains full calculation precision."""
    if isinstance(value, dict):
        return {key: compact_context(item) for key, item in value.items()}
    if isinstance(value, list):
        return [compact_context(item) for item in value]
    if isinstance(value, float):
        return round(value, 3)
    return value


def _data_prompt(label: str, context: dict) -> str:
    return f"{label} (JSON):\n{json.dumps(compact_context(context), ensure_ascii=False, default=str, allow_nan=False, separators=(",", ":"))}"


def _required_text(payload: dict, field: str) -> str:
    value = payload.get(field)
    if isinstance(value, list):
        value = "\n\n".join(str(item).strip() for item in value if str(item).strip())
    if not isinstance(value, str) or not value.strip():
        raise LlmResponseFormatError(f"LLM response is missing the '{field}' text.")
    return value.strip()
