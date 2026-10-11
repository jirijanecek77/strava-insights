"""Versioned coaching prompts and validation of the model's JSON answers."""

import json
from dataclasses import dataclass

from app.services.coaching.llm_client import LlmResponseFormatError

PROMPT_VERSION = "2"

_COACH_PERSONA = (
    "You are an experienced endurance coach for running and cycling who analyses training data. You write in "
    "English, addressing the athlete directly as \"you\". Your tone is honest, specific, and constructive, like a "
    "coach who knows the athlete well: point out what went well and what did not. Ground every statement in the "
    "data provided and quote the numbers that support it; never invent numbers, conditions, feelings, or events "
    "that are not in the data. If heart-rate thresholds or heart-rate data are missing, do not guess training "
    "zones and say that the conclusion is limited. Avoid medical advice. Use metric units."
)

ACTIVITY_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training activity as JSON, together with the athlete's recent training. "streams" holds the activity
downsampled into fixed moving-time intervals: each row lists the moving time and distance at the end of the
interval, the pace or speed and average heart rate within it, and the altitude at its end. "splits" holds the same
data per fixed distance.

Analyse the session rather than retelling it:

1. Session quality: identify the session type and judge how well it was executed for that purpose. Use the streams
   to assess pacing (even, negative or positive split, surges, fade), heart-rate response to the pace, the effect of
   climbs and descents, and how much time was spent in each heart-rate zone versus what the session type calls for.
2. Fatigue: look for signs of fatigue or freshness, such as heart-rate drift at a steady pace (aerobic decoupling),
   a fading pace in the second half, a heart rate that is high or low for the pace compared with recent similar
   sessions, and the load and rest days of recent training.
3. Trends: compare the session with the recent activities, best efforts, and route comparison to say whether fitness
   or efficiency is improving, stable, or declining. Say so plainly when the data is too thin for a trend.

Respond with a single JSON object with exactly these string fields:

- "description": the analysis in 3 short paragraphs (50-100 words), one for session quality, one for fatigue, and
  one for trends, each supported by concrete numbers from the data.
- "summary": 1-2 sentences (at most 40 words) with the analytic verdict: session type, execution quality, fatigue
  signal, and trend. It will later be combined with other summaries into weekly and monthly reviews.
- "recommendation": 2-4 sentences with concrete guidance for the next training session(s) that follows from the
  analysis: session type, duration, and intensity, with heart-rate or pace targets when thresholds are known, and
  whether the athlete should recover or can add load.

Return only the JSON object."""

PERIOD_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training {{period_label}} as JSON: totals per sport, the totals of the previous {{period_label}}, and
every activity with its coaching summary when one exists. The coaching summaries are analyses of single sessions;
use them to judge the {{period_label}} as a whole instead of listing them. Respond with a single JSON object with
exactly these string fields:

- "summary": an analysis of the {{period_label}} (50-100 words) covering training quality (purposeful sessions,
  balance of easy and hard work, how well key sessions were executed), fatigue and recovery (load versus the previous
  {{period_label}}, rest days, recurring fatigue signals), and trends in volume, consistency, and fitness. If
  "in_progress" is true, make clear that the {{period_label}} is not finished yet and analyse it "so far".
- "recommendation": 2-4 sentences on what to focus on in the {{next_period_label}} that follow from the analysis:
  concrete session types, volume, intensity, and recovery guidance.

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


def _data_prompt(label: str, context: dict) -> str:
    return f"{label} (JSON):\n{json.dumps(context, ensure_ascii=False, default=str)}"


def _required_text(payload: dict, field: str) -> str:
    value = payload.get(field)
    if isinstance(value, list):
        value = "\n\n".join(str(item).strip() for item in value if str(item).strip())
    if not isinstance(value, str) or not value.strip():
        raise LlmResponseFormatError(f"LLM response is missing the '{field}' text.")
    return value.strip()
