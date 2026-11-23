import pytest
from app.services.planning.policy import training_bounds, validate_plan
from copy import deepcopy
from datetime import date, timedelta

TODAY = date(2026, 11, 10)
THRESHOLDS = {
    "aet_heart_rate_bpm": 145,
    "ant_heart_rate_bpm": 170,
    "aet_pace_min_per_km": 5.5,
}


def established_training():
    training = []
    for week in range(6):
        for offset in (0, 1, 3, 4, 6):
            distance = 20 if offset == 6 else 10
            training.append(
                {
                    "date": (TODAY - timedelta(days=week * 7 + offset)).isoformat(),
                    "sport": "Run",
                    "distance_km": distance,
                    "pace_seconds_per_km": 330,
                    "hr_bpm": 140,
                    "moving_minutes": distance * 5.5,
                    "elevation_gain_meters": distance * 5,
                }
            )
    return sorted(training, key=lambda a: a["date"])


def test_stable_established_training_builds_modestly_with_normal_frequency_and_long_run():
    bounds = training_bounds(established_training(), THRESHOLDS, TODAY)
    objective = bounds["weekly_objective"]
    assert objective["mode"] == "build"
    assert 60 < objective["distance_min_km"] < objective["distance_max_km"] <= 66
    assert objective["target_running_days"] == 5
    assert 18 <= objective["long_run_min_km"] <= 22
    assert bounds["min_quality_days"] == 1


def test_isolated_fatigue_keeps_volume_and_requires_local_recovery():
    training = established_training()
    training[-1]["hr_bpm"] = 147
    bounds = training_bounds(training, THRESHOLDS, TODAY)
    objective = bounds["weekly_objective"]
    assert objective["mode"] == "maintain"
    assert objective["current_response"]["adverse_dates"] == [TODAY.isoformat()]
    assert objective["distance_min_km"] >= 57
    assert "isolated" in objective["reason"]


def test_repeated_fatigue_allows_evidence_based_recovery_cutback():
    training = established_training()
    for a in training:
        if a["date"] in {TODAY.isoformat(), (TODAY - timedelta(days=1)).isoformat()}:
            a["hr_bpm"] = 147
    bounds = training_bounds(training, THRESHOLDS, TODAY)
    objective = bounds["weekly_objective"]
    assert objective["mode"] == "recover"
    assert len(objective["evidence"]) == 2
    assert objective["distance_max_km"] <= 48
    assert bounds["max_quality_days"] == 0


def test_cycling_load_counts_toward_recovery_objective():
    training = established_training() + [
        {
            "date": TODAY.isoformat(),
            "sport": "Ride",
            "distance_km": 100,
            "pace_seconds_per_km": None,
            "hr_bpm": 140,
            "moving_minutes": 240,
        }
    ]
    objective = training_bounds(training, THRESHOLDS, TODAY)["weekly_objective"]
    assert objective["mode"] == "recover"
    assert "all-sport" in objective["reason"]


def test_new_activity_recalculates_objective_and_dates_from_completed_training():
    training = established_training()
    previous = training_bounds(training, THRESHOLDS, TODAY)["weekly_objective"]
    tomorrow = TODAY + timedelta(days=1)
    training.append(
        dict(training[-1], date=tomorrow.isoformat(), distance_km=8, moving_minutes=44)
    )
    next_objective = training_bounds(training, THRESHOLDS, tomorrow)["weekly_objective"]
    assert previous["mode"] == "build"
    assert next_objective["mode"] == "maintain"
    assert next_objective["block_start"] == "2026-11-12"
    assert next_objective["review_date"] == "2026-11-19"
    assert not next_objective["continued"]


def test_new_recovery_evidence_reduces_a_fresh_forecast():
    training = established_training()
    previous = training_bounds(training, THRESHOLDS, TODAY)["weekly_objective"]
    tomorrow = TODAY + timedelta(days=1)
    training.append(
        {
            "date": tomorrow.isoformat(),
            "sport": "Ride",
            "distance_km": 100,
            "pace_seconds_per_km": None,
            "hr_bpm": 150,
            "moving_minutes": 300,
        }
    )
    objective = training_bounds(training, THRESHOLDS, tomorrow)["weekly_objective"]
    assert objective["mode"] == "recover"
    assert objective["distance_max_km"] < previous["distance_max_km"]
    following = training_bounds(training, THRESHOLDS, tomorrow + timedelta(days=1))[
        "weekly_objective"
    ]
    assert following["review_date"] == "2026-11-20"
    assert not following["continued"]


def test_objective_is_reassessed_after_its_review_date():
    previous = training_bounds(established_training(), THRESHOLDS, TODAY)[
        "weekly_objective"
    ]
    updated = training_bounds(established_training(), THRESHOLDS, TODAY)[
        "weekly_objective"
    ]
    assert updated["mode"] == "build"
    assert not updated["continued"]
    assert date.fromisoformat(updated["review_date"]) > TODAY


def test_different_terrain_and_one_reference_run_do_not_create_fatigue_evidence():
    training = established_training()
    training[-1].update(hr_bpm=148, elevation_gain_meters=500)
    objective = training_bounds(training, THRESHOLDS, TODAY)["weekly_objective"]
    assert TODAY.isoformat() not in objective["current_response"]["adverse_dates"]


def test_build_plan_must_keep_weekly_volume_long_run_and_quality_stimulus():
    bounds = training_bounds(established_training(), THRESHOLDS, TODAY)
    dates = [(TODAY + timedelta(days=i)).isoformat() for i in range(1, 8)]
    days = [
        {
            "date": day,
            "kind": "rest",
            "focus": "rest",
            "distance_km": None,
            "pace_seconds_per_km": None,
            "heart_rate_bpm": None,
            "rationale": "Rest between training sessions.",
        }
        for day in dates
    ]
    for i, distance, focus in [
        (0, 8, "threshold"),
        (2, 11, "easy"),
        (3, 21, "long"),
        (5, 11, "easy"),
        (6, 11, "easy"),
    ]:
        days[i].update(
            kind="run",
            focus=focus,
            distance_km=distance,
            pace_seconds_per_km=300 if i == 0 else 345,
            heart_rate_bpm=160 if i == 0 else 140,
            rationale="Continue the build objective with balanced training.",
        )
    ctx = {"dates": dates, "bounds": bounds}
    assert validate_plan({"days": days}, ctx)
    collapsed = deepcopy(days)
    for d in collapsed:
        if d["kind"] == "run":
            d["distance_km"] *= 0.6
    with pytest.raises(ValueError, match="weekly objective minimum"):
        validate_plan({"days": collapsed}, ctx)
    too_short = deepcopy(days)
    too_short[3]["distance_km"] = 17
    too_short[2]["distance_km"] = 15
    with pytest.raises(ValueError, match="long-run"):
        validate_plan({"days": too_short}, ctx)
    no_quality = deepcopy(days)
    no_quality[0].update(focus="easy", pace_seconds_per_km=345, heart_rate_bpm=140)
    with pytest.raises(ValueError, match="quality session"):
        validate_plan({"days": no_quality}, ctx)
