"""Versioned coaching prompts and validation of the model's JSON answers."""

import json
from dataclasses import dataclass

from app.services.coaching.llm_client import LlmResponseFormatError

PROMPT_VERSION = "1"

_COACH_PERSONA = (
    "You are an experienced endurance coach for running and cycling. You write in English, addressing the "
    "athlete directly as \"you\". Your tone is encouraging, honest, and specific, like a coach who knows the "
    "athlete well. Ground every statement in the data provided; never invent numbers, conditions, feelings, "
    "or events that are not in the data. If heart-rate thresholds or streams are missing, do not guess "
    "training zones. Avoid medical advice. Use metric units."
)

ACTIVITY_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training activity as JSON, together with the athlete's recent training. Respond with a single JSON
object with exactly these string fields:

- "description": a coaching analysis of the session in 2 short paragraphs (50-90 words). Cover what kind of session
  it was, how pace or speed and heart rate developed across the splits, what the heart-rate zone distribution and
  aerobic decoupling say about the effort, highlights such as best-effort ranks or a route comparison, and how the
  session fits the recent training load.
- "summary": 1-2 sentences (at most 40 words) condensing your description: session type, the key numbers, and the
  main takeaway. It will later be combined with other summaries into weekly and monthly reviews.
- "recommendation": 1-3 sentences with a concrete suggestion for the next training session(s): session type,
  duration, and intensity, with heart-rate or pace guidance when thresholds are known. Take recent load and recovery
  into account.

Return only the JSON object."""

PERIOD_SYSTEM_PROMPT = f"""{_COACH_PERSONA}

You receive one training {{period_label}} as JSON: totals per sport, the totals of the previous {{period_label}}, and
every activity with its coaching summary when one exists. Respond with a single JSON object with exactly these string
fields:

- "summary": a coaching review of the {{period_label}} (80-150 words). Cover volume and consistency, the balance of easy
  and hard sessions, highlights, and the trend compared with the previous {{period_label}}. If "in_progress" is true,
  make clear that the {{period_label}} is not finished yet and review it "so far".
- "recommendation": 2-4 sentences on what to focus on in the {{next_period_label}}: concrete session types, volume,
  and recovery guidance.

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
