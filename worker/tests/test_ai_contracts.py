import pytest
from ai_fixtures import load_cases
from pydantic import ValidationError

from app.services.ai.contracts import (
    ActivityContext,
    ActivityResult,
    PeriodContextData,
    PeriodResult,
    PlanningContext,
    PlanResult,
)
from app.services.coaching.contracts import ActivityEvaluation, PeriodEvaluation


@pytest.mark.parametrize(
    "case",
    load_cases(),
    ids=lambda case: case.id,
)
def test_current_contexts_round_trip_without_losing_precision_or_missing_meanings(case):
    model = {
        "activity": ActivityContext,
        "week": PeriodContextData,
        "month": PeriodContextData,
        "plan": PlanningContext,
    }[case.kind]
    parsed = model.model_validate(case.context)
    assert parsed.model_dump(mode="json", exclude_unset=True) == case.context


@pytest.mark.parametrize(
    "model,payload",
    [
        (ActivityResult, {"description": "x", "summary": " ", "recommendation": "x"}),
        (
            ActivityResult,
            {"description": "x", "summary": "x", "recommendation": "x", "extra": "x"},
        ),
        (ActivityResult, {"description": [], "summary": "x", "recommendation": "x"}),
        (PeriodResult, {"summary": "x"}),
        (PeriodResult, {"summary": " ", "recommendation": "x"}),
        (PeriodResult, {"summary": "x", "recommendation": "x", "days": []}),
    ],
)
def test_new_results_reject_invalid_provider_shapes(model, payload):
    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_legacy_coaching_readers_preserve_text_and_numeric_handoffs():
    legacy = {
        "period_type": "week",
        "period_start": "2026-11-02",
        "status": "ready",
        "summary": "Original text.",
        "recommendation": "Original advice.",
        "metrics": {"old_field": 1.123456789},
    }
    assert (
        PeriodEvaluation.model_validate(legacy).model_dump(mode="json")["metrics"]
        == legacy["metrics"]
    )
    assert PeriodEvaluation.model_validate(legacy).summary == "Original text."


def test_new_plan_contract_requires_exactly_seven_days():
    with pytest.raises(ValidationError):
        PlanResult.model_validate({"days": []})
