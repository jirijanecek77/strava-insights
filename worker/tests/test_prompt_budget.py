"""Golden input-token ceilings measured before planning prompt version 3 (o200k_harmony)."""

import pytest
import tiktoken
from app.services.planning.policy import build_prompt, training_bounds
from datetime import timedelta

from test_planning_objective import THRESHOLDS, TODAY, established_training


@pytest.mark.parametrize("per_day,old_tokens", [(0, 2803), (1, 4261), (3, 10118)])
def test_new_planning_input_never_exceeds_recorded_previous_prompt(per_day, old_tokens):
    activities = (
        established_training()
        if per_day == 0
        else [
            dict(
                established_training()[0],
                date=str(TODAY - timedelta(days=i)),
                coaching_summary="Steady aerobic effort with controlled pacing and no clear fatigue signal.",
            )
            for i in range(42)
            for _ in range(per_day)
        ]
    )
    activities = [
        dict(
            activity,
            coaching_status=(
                "ready" if activity.get("coaching_summary") else "unavailable"
            ),
        )
        for activity in activities
    ]
    bounds = training_bounds(activities, THRESHOLDS, TODAY)
    objective = bounds.pop("weekly_objective")
    system, user = build_prompt(
        dict(
            today=str(TODAY),
            dates=[str(TODAY + timedelta(days=i)) for i in range(1, 8)],
            timezone="Europe/Prague",
            thresholds=THRESHOLDS,
            activities=activities,
            bounds=bounds,
            weekly_objective=objective,
            policy_version="3",
        )
    )
    encoding = tiktoken.get_encoding("o200k_harmony")
    tokens = (
            sum(
                len(encoding.encode(text, disallowed_special=())) for text in (system, user)
            )
            + 32
    )
    assert tokens <= old_tokens


@pytest.mark.parametrize(
    "kind,old_tokens", [("activity", 524), ("week", 486), ("month", 486)]
)
def test_clearer_coaching_json_instructions_fit_the_previous_token_budget(
        kind, old_tokens
):
    import json

    from app.services.coaching.prompts import build_activity_prompt, build_period_prompt

    system, _ = (
        build_activity_prompt({})
        if kind == "activity"
        else build_period_prompt(
            {
                "period_type": kind,
                "in_progress": True,
            }
        )
    )
    example, _ = json.JSONDecoder().raw_decode(system[system.index("{"):])
    assert set(example) == (
        {"description", "summary", "recommendation"}
        if kind == "activity"
        else {"summary", "recommendation"}
    )
    assert all(isinstance(value, str) and value for value in example.values())
    encoding = tiktoken.get_encoding("o200k_harmony")
    assert len(encoding.encode(system, disallowed_special=())) <= old_tokens
