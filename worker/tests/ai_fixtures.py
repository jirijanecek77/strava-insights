"""Synthetic inputs shared by application, schema and provider regressions."""

from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter

from app.services.ai.contracts import (
    ActivityContext,
    Context,
    InputSnapshot,
    Operation,
    PeriodContextData,
    PlanningContext,
    WorkClaim,
)
from app.services.coaching.evidence import fingerprint
from app.services.coaching.prompts import (
    ACTIVITY_PROMPT_VERSION,
    PROMPT_VERSION,
    build_activity_prompt,
    build_period_prompt,
)
from app.services.planning.policy import PROMPT_VERSION as PLAN_VERSION
from app.services.planning.policy import build_prompt


class ContextExample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: Operation
    today: date
    context: dict[str, JsonValue]


@lru_cache(maxsize=1)
def load_cases() -> tuple[ContextExample, ...]:
    path = Path(__file__).parent / "fixtures" / "ai_contexts.json"
    return tuple(TypeAdapter(list[ContextExample]).validate_json(path.read_bytes()))


def snapshot_for(case_id: str) -> InputSnapshot:
    case = next(case for case in load_cases() if case.id == case_id)
    context: Context
    if case.kind == Operation.ACTIVITY:
        context = ActivityContext.model_validate(case.context)
        system, user = build_activity_prompt(case.context)
        version = ACTIVITY_PROMPT_VERSION
    elif case.kind in {Operation.WEEK, Operation.MONTH}:
        context = PeriodContextData.model_validate(case.context)
        system, user = build_period_prompt(case.context)
        version = PROMPT_VERSION
    else:
        context = PlanningContext.model_validate(case.context)
        system, user = build_prompt(case.context)
        version = PLAN_VERSION
    return InputSnapshot(
        WorkClaim(case.kind, load_cases().index(case), -1, "test-claim", 0),
        context,
        fingerprint(case.context),
        fingerprint([system, user]),
        system,
        user,
        version,
        case.today,
    )
