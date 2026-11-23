from copy import deepcopy

import pytest
from ai_fixtures import snapshot_for

from app.services.planning.policy import validate_plan


@pytest.mark.parametrize(
    "case_id,mode,distances",
    [
        ("plan-supported", "build", {0: 8.5, 2: 8.5, 5: 8.2}),
        ("plan-recovery", "recover", {1: 6, 4: 6}),
    ],
)
def test_build_and_recovery_forecasts_validate_feasible_targets_and_reject_excess(
    case_id, mode, distances
):
    context = snapshot_for(case_id).context.model_dump(mode="json")
    assert context["weekly_objective"]["mode"] == mode
    days = [
        {
            "date": day,
            "kind": "run" if index in distances else "rest",
            "focus": "easy" if index in distances else "rest",
            "distance_km": distances.get(index),
            "pace_seconds_per_km": 345 if index in distances else None,
            "heart_rate_bpm": 140 if index in distances else None,
            "rationale": "Bounded training scenario.",
        }
        for index, day in enumerate(context["dates"])
    ]
    assert validate_plan({"days": days}, context) == days
    invalid = deepcopy(days)
    invalid[next(iter(distances))]["distance_km"] = (
        context["bounds"]["max_run_distance_km"] + 1
    )
    with pytest.raises(ValueError):
        validate_plan({"days": invalid}, context)
