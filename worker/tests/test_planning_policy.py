from copy import deepcopy
from datetime import date, timedelta

import pytest

from app.services.planning.policy import (
    InsufficientTrainingData,
    training_bounds,
    validate_plan,
)

TODAY = date(2026, 11, 10)


def activities():
    return [
        {
            "date": (TODAY - timedelta(days=i)).isoformat(),
            "sport": "Run",
            "distance_km": 10,
            "pace_seconds_per_km": 330,
            "hr_bpm": 140,
        }
        for i in [2, 4, 6, 9, 11, 13]
    ]


def context():
    return {
        "dates": [(TODAY + timedelta(days=i)).isoformat() for i in range(1, 8)],
        "bounds": training_bounds(
            activities(), {"aet_heart_rate_bpm": 145, "ant_heart_rate_bpm": 170}, TODAY
        ),
    }


def payload():
    return {
        "days": [
            {
                "date": d,
                "kind": "run" if i in (0, 3, 5) else "rest",
                "focus": "easy" if i in (0, 3, 5) else "rest",
                "distance_km": 10 if i in (0, 3, 5) else None,
                "pace_seconds_per_km": 345 if i in (0, 3, 5) else None,
                "heart_rate_bpm": 140 if i in (0, 3, 5) else None,
                "rationale": (
                    "Build aerobic endurance." if i in (0, 3, 5) else "Recover."
                ),
            }
            for i, d in enumerate(context()["dates"])
        ]
    }


def test_balanced_plan_allows_recovery_and_does_not_require_increasing_volume():
    plan = payload()
    assert validate_plan(plan, context()) == plan["days"]
    assert sum(d["distance_km"] or 0 for d in plan["days"]) == 30


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p["days"].pop(),
        lambda p: p["days"][0].update(date=p["days"][1]["date"]),
        lambda p: p["days"][0].update(distance_km=float("nan")),
        lambda p: p["days"][0].update(distance_km=12),
        lambda p: p["days"][0].update(distance_km=True),
        lambda p: p["days"][0].update(heart_rate_bpm=145.1),
        lambda p: p["days"][0].update(heart_rate_bpm=180),
        lambda p: p["days"][0].update(pace_seconds_per_km=200),
        lambda p: p["days"][1].update(distance_km=0),
    ],
)
def test_invalid_or_unsupported_targets_are_rejected(mutation):
    plan = payload()
    mutation(plan)
    with pytest.raises(ValueError):
        validate_plan(plan, context())


def test_weekly_volume_limit_is_enforced():
    plan = payload()
    for i in (0, 2, 4, 6):
        plan["days"][i] = dict(
            plan["days"][0], date=context()["dates"][i], distance_km=10
        )
    plan["days"][3] = dict(payload()["days"][1], date=context()["dates"][3])
    plan["days"][5] = dict(payload()["days"][1], date=context()["dates"][5])
    with pytest.raises(ValueError, match="volume"):
        validate_plan(plan, context())


def test_cycling_fatigue_requires_recovery_before_quality_work():
    training = activities() + [
        {
            "date": TODAY.isoformat(),
            "sport": "Ride",
            "distance_km": 70,
            "pace_seconds_per_km": None,
            "hr_bpm": 155,
        }
    ]
    ctx = context()
    ctx["bounds"] = training_bounds(
        training, {"aet_heart_rate_bpm": 145, "ant_heart_rate_bpm": 170}, TODAY
    )
    plan = payload()
    plan["days"][0].update(focus="threshold", distance_km=9, heart_rate_bpm=165)
    plan["days"][3]["distance_km"] = 10.5
    plan["days"][5]["distance_km"] = 10.5
    with pytest.raises(ValueError, match="recovery spacing"):
        validate_plan(plan, ctx)
    plan["days"][0].update(focus="easy", heart_rate_bpm=140)
    assert validate_plan(plan, ctx)


def test_no_thresholds_only_allows_easy_work_using_observed_hr():
    bounds = training_bounds(activities(), {}, TODAY)
    assert bounds["max_quality_days"] == 0
    assert bounds["easy_hr_ceiling_bpm"] == 140


@pytest.mark.parametrize("training,thresholds", [([], {}), (activities(), {})])
def test_insufficient_recent_running_or_hr_is_explicit(training, thresholds):
    without_hr = [dict(a, hr_bpm=None) for a in training]
    with pytest.raises(InsufficientTrainingData):
        training_bounds(without_hr, thresholds, TODAY)


def test_active_runner_plan_cannot_arbitrarily_collapse_volume():
    plan = payload()
    for day in plan["days"]:
        if day["kind"] == "run":
            day["distance_km"] = 1
    with pytest.raises(ValueError, match="weekly objective minimum"):
        validate_plan(plan, context())


def test_cycling_load_spike_allows_larger_recovery_cutback():
    training = [dict(a, moving_minutes=55) for a in activities()]
    training.append(
        {
            "date": TODAY.isoformat(),
            "sport": "Ride",
            "distance_km": 100,
            "pace_seconds_per_km": None,
            "hr_bpm": 150,
            "moving_minutes": 240,
        }
    )
    bounds = training_bounds(
        training, {"aet_heart_rate_bpm": 145, "ant_heart_rate_bpm": 170}, TODAY
    )
    assert bounds["recovery_load_spike"]
    assert bounds["weekly_objective"]["mode"] == "recover"
    assert 0 < bounds["min_weekly_distance_km"] < 25


def test_return_after_inactivity_allows_small_easy_plan():
    training = [
        dict(a, date=(TODAY - timedelta(days=i)).isoformat())
        for a, i in zip(activities()[:3], [8, 10, 12])
    ]
    bounds = training_bounds(
        training, {"aet_heart_rate_bpm": 145, "ant_heart_rate_bpm": 170}, TODAY
    )
    assert bounds["min_weekly_distance_km"] == 0
    assert bounds["max_quality_days"] == 0


def test_easy_pace_cannot_contradict_aerobic_threshold():
    ctx = context()
    ctx["bounds"] = training_bounds(
        activities(),
        {
            "aet_heart_rate_bpm": 145,
            "ant_heart_rate_bpm": 170,
            "aet_pace_min_per_km": 5.5,
        },
        TODAY,
    )
    plan = payload()
    plan["days"][0]["pace_seconds_per_km"] = 310
    with pytest.raises(ValueError, match="aerobic pace baseline"):
        validate_plan(plan, ctx)
