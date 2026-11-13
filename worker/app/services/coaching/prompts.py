"""Versioned coaching prompts and validation of the model's JSON answers."""

import json
from dataclasses import dataclass

from app.services.coaching.llm_client import LlmResponseFormatError

PROMPT_VERSION = "3"
ACTIVITY_PROMPT_VERSION = "4"

_COACH_PERSONA = (
    "You are an experienced endurance coach for running and cycling who analyses training data. You write in "
    'English, addressing the athlete directly as "you". Your tone is honest, specific, and constructive, like a '
    "coach who knows the athlete well: point out what went well and what did not. Ground every statement in the "
    "data provided; use numerical comparisons only when needed to explain a finding; never invent numbers, conditions, feelings, or events "
    "that are not in the data. If heart-rate thresholds or heart-rate data are missing, do not guess training "
    "zones and say that the conclusion is limited. Avoid medical advice. Use metric units."
)

ACTIVITY_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training activity as JSON, together with the athlete's recent training. "splits" contains the
chronological recorded Garmin laps, preserving auto-laps and workout/manual intervals, including short final laps.
Each row gives lap distance and timer duration, average running pace or cycling speed, average heart rate when
available, and a recorded lap type when available. Timed recoveries remain included; timer stops are excluded.
These are lap averages, not stream samples. No stream excerpts or elevation profile are supplied. Do not infer
within-lap surges or HR response timing from averages. Compact terrain aggregates are supplied when available;
these are locally calculated context, not an elevation profile. A lap type alone does not establish a
workout's purpose. If split_data_limitation is present, state the limitation and use only available evidence.

Interpret the session without repeating displayed KPIs: do not recap distance, duration, average pace/HR, or total
ascent in the description or summary. The athlete can read these above the coaching card. Explain what the evidence
means for execution, effort, and training. Structured activity_evidence supplies reusable facts for period reviews.

Use total elevation gain and lap/final-section terrain_context to contextualize pace and HR changes. An uphill finish
can explain late slowing or higher HR; neither alone demonstrates fatigue. Total ascent cannot locate a hill. Missing
or partial terrain coverage is not evidence of flat terrain: qualify any fatigue conclusion. Never claim terrain
proves fatigue is absent. Treat a tempo candidate as a sustained intensity block, not proof of deliberate workout intent.

Analyse the session rather than retelling it:

1. Session quality: identify the session type when supported and judge how well it was executed for that purpose.
   Compare lap pace or speed and average HR to assess even pacing, progression, repeated work/recovery intervals,
   or fade. Account for unequal lap distances/durations. Use supplied aggregate heart-rate zone shares when present.
2. Fatigue: look for signs of fatigue or freshness, such as supplied aerobic decoupling at a steady pace,
   a fading pace in the second half, a heart rate that is high or low for the pace compared with recent similar
   sessions, and the load and rest days of recent training.
3. Trends: compare the session with the recent activities, best efforts, and route comparison to say whether fitness
   or efficiency is improving, stable, or declining. Say so plainly when the data is too thin for a trend.

Respond with a single JSON object with exactly these string fields:

- "description": the analysis in 3 short paragraphs (50-100 words), one for session quality, one for fatigue, and
  one for trends. Provide interpretation, not a KPI recap; numbers are optional and only for meaningful comparisons.
- "summary": 1-2 sentences (at most 40 words) with the analytic verdict: session type, execution quality, fatigue
  signal, and trend. It will later be combined with other summaries into weekly and monthly reviews.
- "recommendation": 2-4 sentences with concrete guidance for the next training session(s) that follows from the
  analysis: session type, duration, and intensity, with heart-rate or pace targets when thresholds are known, and
  whether the athlete should recover or can add load.

Return only the JSON object."""

PERIOD_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training {{period_label}} as JSON: totals per sport, the totals of the previous {{period_label}}, and
a bounded selection of activity digests with coaching summaries when available. Totals cover all activities.
The coaching summaries are analyses of single sessions;
use them to judge the {{period_label}} as a whole instead of listing them. Respond with a single JSON object with
exactly these string fields:

- "summary": an analysis of the {{period_label}} ({{word_range}} words) covering training quality (purposeful sessions,
  balance of easy and hard work, how well key sessions were executed), fatigue and recovery (load versus the previous
  {{period_label}}, rest days, recurring fatigue signals), and trends in volume, consistency, and fitness. If
  "in_progress" is true, make clear that the {{period_label}} is not finished yet and analyse it "so far".
- "recommendation": 2-4 sentences on what to focus on in the {{next_period_label}} that follow from the analysis:
  concrete session types, volume, intensity, and recovery guidance.

Period facts are authoritative. Activity digests are bounded interpretations, not a complete list, and may contain
older unsupported fatigue claims: do not repeat them when terrain/comparable evidence is missing. Do not sum narrative
numbers. Use comparison_windows; for unfinished periods compare the supplied matching elapsed windows, not the full
prior period. State unequal calendar exposure when current_days differs from previous_days.

For both weeks and months explicitly report time (h:mm:ss) and distance (km) for all three HR bands for running:
below AeT, AeT to below AnT, and at/above AnT. Use hr_bands_by_sport.Run; if running is absent, use available sports
separately labelled. A null is unavailable, not zero. Mention partial/unknown coverage; these are measured totals,
not an exact allocation of all moving time. Never use lap-average HR to invent band totals.

For months explicitly compare total and running HR-band distances with previous-period data and discuss endurance
and tempo separately using performance_comparison. At least two independent matched pairs are required for a trend;
one pair is tentative and no pairs means insufficient data. Explain improved pace at comparable HR or longer sustained
effort where supported. Higher volume alone does not show fitness improvement. Do not interpret HR threshold setting
changes as fitness gains. Do not infer steady-effort fatigue from interval-session decoupling.

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
        word_range="120-180" if is_week else "150-220",
        next_period_label=(
            ("rest of the week" if is_week else "rest of the month")
            if context.get("in_progress")
            else ("next week" if is_week else "next month")
        ),
    )
    return system_prompt, _data_prompt("Training period data", context)


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
