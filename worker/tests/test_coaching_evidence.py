from copy import deepcopy
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.services.coaching.evidence import (
    aggregate_evidence,
    band_totals,
    build_evidence,
    compare_performance,
    lap_evidence,
    terrain_section,
    threshold_values,
)
from app.services.coaching.context_builder import CoachingContextBuilder
from app.services.coaching.metrics import heart_rate_zone_shares
from app.services.coaching.prompts import build_activity_prompt
from test_coaching_context_builder import RepositoryStub, _activity


def stream(times, distances, hrs, altitudes=None):
    return SimpleNamespace(
        time_stream={"data": times},
        distance_stream={"data": distances},
        heartrate_stream={"data": hrs},
        altitude_stream={"data": altitudes or []},
    )


def test_band_boundaries_and_partial_independent_distance_coverage():
    activity = _activity(1, datetime.now(UTC), moving_time=60, distance="200")
    data = stream(
        [0, 10, 20, 30, 40, 50, 60],
        [0, 30, 60, 90],
        [100, 139, 140, 165, None, 0, float("nan")],
    )
    result = band_totals(activity, data, {"aet_hr_bpm": 140, "ant_hr_bpm": 165})
    assert result["bands"] == {
        "below_aet": {"time_s": 10, "distance_m": 30},
        "between_aet_ant": {"time_s": 10, "distance_m": 30},
        "above_ant": {"time_s": 10, "distance_m": 30},
    }
    assert result["coverage"] == {
        "classified_time_s": 30,
        "classified_distance_m": 90,
        "unknown_time_s": 30,
        "unknown_distance_m": 110,
    }
    result = band_totals(
        activity,
        stream([0, 10, 20], [], [100, 140, 165]),
        {"aet_hr_bpm": 140, "ant_hr_bpm": 165},
    )
    assert result["bands"]["between_aet_ant"] == {"time_s": 10, "distance_m": None}
    assert result["bands"]["above_ant"]["time_s"] == 10
    shares = heart_rate_zone_shares(
        time_seconds=[0, 10, 20],
        heartrate_bpm=[100, 140, 165],
        aet_heart_rate_bpm=140,
        ant_heart_rate_bpm=165,
    )
    assert shares["above_ant_percent"] == 50


def test_invalid_thresholds_pauses_gaps_and_resets_never_fill_missing_coverage():
    activity = _activity(1, datetime.now(UTC), moving_time=1000, distance="1000")
    data = stream(
        [0, 10, 20, 500, 510, 520, 530], [0, 30, 30, 900, 0, 30, 60], [130] * 7
    )
    result = band_totals(activity, data, {"aet_hr_bpm": 140, "ant_hr_bpm": 165})
    assert result["coverage"]["classified_time_s"] == 30
    assert result["coverage"]["classified_distance_m"] == 90
    missing = band_totals(activity, data, None)
    assert all(row["time_s"] is None for row in missing["bands"].values())
    assert (
        threshold_values(
            SimpleNamespace(aet_heart_rate_bpm=165, ant_heart_rate_bpm=140)
        )
        is None
    )
    assert (
        threshold_values(
            SimpleNamespace(aet_heart_rate_bpm=float("nan"), ant_heart_rate_bpm=165)
        )
        is None
    )
    excess = band_totals(
        _activity(2, datetime.now(UTC), moving_time=1, distance="1"),
        data,
        {"aet_hr_bpm": 140, "ant_hr_bpm": 165},
    )
    assert any("exceeds" in text for text in excess["limitations"])
    assert excess["coverage"]["unknown_time_s"] == 0


def test_uphill_finish_terrain_is_local_compact_context_without_raw_samples():
    repo = RepositoryStub()
    times = list(range(0, 3001, 10))
    distances = [time * 10 / 3 for time in times]
    altitudes = [100 + max(0, distance - 8000) * 0.1 for distance in distances]
    data = stream(times, distances, [140] * len(times), altitudes)
    repo.get_stream = lambda _: data
    context = CoachingContextBuilder(repo).build_activity_context(
        user_id=1, activity_id=10
    )
    assert context["activity"]["elevation_gain_m"] == 85
    finish = context["terrain_context"]["finish"]
    assert finish["net_grade_pct"] == pytest.approx(10)
    assert finish["ascent_m"] == pytest.approx(200, abs=4)
    assert finish["coverage_fraction"] > 0.95
    assert terrain_section(None, 8000, 10000)["net_grade_pct"] is None
    system, payload = build_activity_prompt(context)
    assert "without repeating displayed KPIs" in system
    assert "uphill finish" in system
    assert "cannot locate a hill" in system
    assert "altitude_stream" not in payload and "latlng" not in payload
    noisy = stream([], list(range(0, 101, 20)), [], [100, 101, 100, 101, 100, 101])
    assert terrain_section(noisy, 0, 100)["ascent_m"] == 0


def test_lap_candidates_exclude_recoveries_and_reject_unsteady_work():
    laps = [
        dict(
            number=i + 1,
            distance_meters=1000,
            duration_seconds=300,
            average_heartrate_bpm=150,
            lap_type="INTERVAL",
        )
        for i in range(4)
    ]
    _, candidates = lap_evidence(
        laps, None, {"aet_hr_bpm": 140, "ant_hr_bpm": 165}, "Run"
    )
    assert candidates["tempo"][0]["duration_s"] == 1200
    laps[1]["lap_type"] = "RECOVERY"
    _, candidates = lap_evidence(
        laps, None, {"aet_hr_bpm": 140, "ant_hr_bpm": 165}, "Run"
    )
    assert candidates["tempo"][0]["lap_range"] == [3, 4]
    laps[3]["duration_seconds"] = 500
    assert (
        lap_evidence(laps, None, {"aet_hr_bpm": 140, "ant_hr_bpm": 165}, "Run")[1][
            "tempo"
        ]
        == []
    )


def sample(activity_id, day, pace=350, hr=150, route=1):
    return {
        "activity_id": activity_id,
        "date": day,
        "sport": "Run",
        "route_group_id": route,
        "threshold_snapshot": {
            "aet_hr_bpm": 140,
            "ant_hr_bpm": 165,
            "effective_from": "2026-01-01",
        },
        "candidates": {
            kind: [
                {
                    "duration_s": 1800,
                    "distance_m": 5000,
                    "pace_s_per_km": pace,
                    "hr_bpm": hr,
                    "net_grade_pct": 0,
                    "ascent_m_per_km": 10,
                }
            ]
            for kind in ("endurance", "tempo")
        },
    }


def test_trends_need_independent_pairs_and_comparable_hr_thresholds_and_terrain():
    old = [sample(1, "2026-10-01"), sample(2, "2026-10-15")]
    current = [sample(3, "2026-11-01", pace=335), sample(4, "2026-11-15", pace=335)]
    assert (
        compare_performance(current[:1], old)["tempo"]["status"] == "insufficient_data"
    )
    assert compare_performance(current, old)["tempo"]["status"] == "improving"
    assert compare_performance(current, old[:1])["tempo"]["matched_pairs"] == 1
    current[1]["threshold_snapshot"]["ant_hr_bpm"] = 170
    assert compare_performance(current, old)["tempo"]["status"] == "insufficient_data"
    current[0]["candidates"]["tempo"][0]["hr_bpm"] = 160
    assert compare_performance(current, old)["tempo"]["matched_pairs"] == 0


def test_month_windows_distance_totals_and_prior_evidence_invalidation():
    repo = RepositoryStub()
    repo.old = _activity(8, datetime(2026, 9, 7, tzinfo=UTC), distance="12000")
    builder = CoachingContextBuilder(repo)
    first = builder.build_period_context(
        user_id=1,
        period_type="month",
        period_start=date(2026, 10, 1),
        today=date(2026, 10, 8),
    )
    assert first.context["comparison_windows"]["previous_end"] == "2026-09-08"
    assert first.context["distance_comparison_by_sport"]["Run"]["change_m"] == 8000
    assert "laps" not in str(first.context)
    repo.old.distance_meters = 11000
    second = builder.build_period_context(
        user_id=1,
        period_type="month",
        period_start=date(2026, 10, 1),
        today=date(2026, 10, 8),
    )
    assert first.source_hash != second.source_hash
    assert second.context["hr_bands_by_sport"]["Run"]["activities"] == 2
    repo.get_threshold_profile = lambda **_: None
    missing = builder.build_period_context(
        user_id=1,
        period_type="week",
        period_start=date(2026, 10, 5),
        today=date(2026, 10, 12),
    )
    assert (
        missing.context["hr_bands_by_sport"]["Run"]["bands"]["below_aet"]["time_s"]
        is None
    )
    assert missing.context["hr_bands_by_sport"]["Run"]["activities_missing_hr"] == 2


def test_calendar_month_clamps_previous_window_and_never_uses_overlapping_weeks():
    repo = RepositoryStub()
    repo.old = _activity(8, datetime(2026, 2, 28, tzinfo=UTC))
    repo.earlier = _activity(9, datetime(2026, 3, 1, tzinfo=UTC))
    repo.current = _activity(10, datetime(2026, 3, 31, tzinfo=UTC))
    context = (
        CoachingContextBuilder(repo)
        .build_period_context(
            user_id=1,
            period_type="month",
            period_start=date(2026, 3, 1),
            today=date(2026, 3, 31),
        )
        .context
    )
    assert context["comparison_windows"]["current_days"] == 31
    assert context["comparison_windows"]["previous_days"] == 28
    assert context["comparison_windows"]["previous_end"] == "2026-02-28"
    assert context["distance_comparison_by_sport"]["Run"]["current_distance_m"] == 20000
    assert (
        context["distance_comparison_by_sport"]["Run"]["previous_distance_m"] == 10000
    )
    assert context["hr_bands_by_sport"]["Run"]["activities"] == 2
