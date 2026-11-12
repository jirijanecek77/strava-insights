import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.coaching.context_builder import (
    CoachingContextBuilder,
    period_bounds,
    period_start_for,
    previous_period_start,
)
from app.services.coaching.llm_client import LlmResponseFormatError
from app.services.coaching.prompts import (
    build_activity_prompt,
    build_period_prompt,
    parse_activity_narrative,
    parse_period_review,
)


def _activity(activity_id: int, start: datetime, *, moving_time: int = 3000, distance: str = "10000", hr: str = "145"):
    return SimpleNamespace(
        id=activity_id,
        user_id=1,
        name=f"Run {activity_id}",
        description=None,
        sport_type="Run",
        source_provider="garmin",
        start_date_utc=start,
        start_date_local=start,
        distance_meters=Decimal(distance),
        distance_km=Decimal(distance) / 1000,
        moving_time_seconds=moving_time,
        elapsed_time_seconds=moving_time + 60,
        total_elevation_gain_meters=Decimal("85"),
        average_speed_mps=Decimal(distance) / moving_time,
        max_speed_mps=Decimal("4.5"),
        average_heartrate_bpm=Decimal(hr),
        average_cadence=Decimal("172"),
        average_pace_seconds_per_km=Decimal(moving_time) * 1000 / Decimal(distance),
    )


class RepositoryStub:
    def __init__(self) -> None:
        self.current = _activity(10, datetime(2026, 10, 7, 7, tzinfo=UTC), moving_time=2900)
        self.earlier = _activity(9, datetime(2026, 10, 5, 7, tzinfo=UTC))
        self.old = _activity(8, datetime(2026, 9, 20, 7, tzinfo=UTC), moving_time=3100)
        self.notes = {
            9: SimpleNamespace(status="ready", summary="Easy recovery run."),
            10: SimpleNamespace(status="pending", summary=None),
        }

    def get_activity(self, *, user_id, activity_id):
        return self.current if activity_id == 10 else None

    def get_stream(self, activity_id):
        times = list(range(0, 2901, 10))
        return SimpleNamespace(
            time_stream={"data": times},
            distance_stream={"data": [seconds * 10000 / 2900 for seconds in times]},
            heartrate_stream={"data": [130 if seconds < 1500 else 160 for seconds in times]},
            altitude_stream={"data": [200 for _ in times]},
        )

    def get_splits(self, activity_id):
        return SimpleNamespace(status="ready", laps=[
            {"number": 1, "lap_type": "WARMUP", "distance_meters": 1890.58, "duration_seconds": 600,
             "average_pace_seconds_per_km": 317.36, "average_speed_kph": 11.344, "average_heartrate_bpm": 144},
            {"number": 2, "lap_type": "INTERVAL", "distance_meters": 400, "duration_seconds": 100,
             "average_pace_seconds_per_km": 250, "average_speed_kph": 14.4, "average_heartrate_bpm": 166},
            {"number": 3, "lap_type": "RECOVERY", "distance_meters": 125, "duration_seconds": 60,
             "average_pace_seconds_per_km": 480, "average_speed_kph": 7.5, "average_heartrate_bpm": None},
        ])

    def get_threshold_profile(self, *, user_id, on_date):
        return SimpleNamespace(
            aet_heart_rate_bpm=140,
            ant_heart_rate_bpm=165,
            aet_pace_min_per_km=Decimal("5.50"),
            ant_pace_min_per_km=Decimal("4.50"),
        )

    def list_best_efforts(self, *, user_id, sport_type):
        return [
            SimpleNamespace(effort_code="10km", best_time_seconds=2850, activity_id=8),
            SimpleNamespace(effort_code="10km", best_time_seconds=2900, activity_id=10),
            SimpleNamespace(effort_code="5km", best_time_seconds=1400, activity_id=10),
        ]

    def list_route_attempts(self, activity_id):
        return [self.current, self.earlier, self.old]

    def list_activities_with_notes(self, *, user_id, start, end):
        start_dt = _as_datetime(start)
        end_dt = _as_datetime(end)
        return [
            (activity, self.notes.get(activity.id))
            for activity in (self.old, self.earlier, self.current)
            if start_dt <= activity.start_date_local < end_dt
        ]


def _as_datetime(value):
    if isinstance(value, datetime):
        return value
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def test_activity_context_combines_metrics_thresholds_efforts_route_and_recent_training() -> None:
    context = CoachingContextBuilder(RepositoryStub()).build_activity_context(user_id=1, activity_id=10)

    assert context is not None
    assert context["activity"]["date"] == "2026-10-07"
    assert "weekday" not in context["activity"]
    assert "start_time_local" not in context["activity"]
    assert "max_speed_kph" not in context["activity"]
    assert context["activity"]["elapsed_time"] == "49:20"
    assert context["activity"]["avg_pace"] == "4:50 /km"
    assert context["activity"]["moving_time"] == "48:20"
    assert "athlete_notes" not in context["activity"]
    assert context["athlete_thresholds"] == {
        "aet_heart_rate_bpm": 140,
        "ant_heart_rate_bpm": 165,
        "aet_pace": "5:30 /km",
        "ant_pace": "4:30 /km",
    }
    assert len(context["splits"]) == 3
    assert context["splits"][0] == {"split": 1, "type": "WARMUP", "distance_km": 1.891,
                                     "duration_seconds": 600, "pace": "5:17 /km", "avg_hr_bpm": 144}
    assert context["splits"][1]["pace"] == "4:10 /km"
    assert "avg_hr_bpm" not in context["splits"][2]
    assert "streams" not in context
    assert "split_data_limitation" not in context
    assert context["heart_rate_zones"]["below_aet_percent"] == pytest.approx(51.7, abs=0.5)
    assert context["aerobic_decoupling_percent"] > 0
    assert context["best_efforts"] == [
        {"distance": "10km", "time": "48:20", "all_time_rank": 2},
        {"distance": "5km", "time": "23:20", "all_time_rank": 1},
    ]
    assert context["route_comparison"] == {
        "attempts_on_this_route": 3,
        "rank_by_moving_time": 1,
        "this_time": "48:20",
        "best_time": "48:20",
        "previous_attempt": {"date": "2026-10-05", "time": "50:00", "avg_hr_bpm": 145},
    }
    recent = context["recent_training"]
    assert recent["days_since_previous_activity"] == 2
    assert [item["date"] for item in recent["activities_last_14_days"]] == ["2026-10-05"]
    assert recent["activities_last_14_days"][0]["coaching_summary"] == "Easy recovery run."
    assert recent["totals_last_28_days_by_sport"]["Run"]["activities"] == 2

    system_prompt, user_prompt = build_activity_prompt(context)
    assert "recommendation" in system_prompt
    assert "Fatigue" in system_prompt
    sent = json.loads(user_prompt.split("\n", 1)[1])
    assert sent["best_efforts"][0]["all_time_rank"] == 2
    assert user_prompt.split("\n", 1)[1] == json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    assert '"altitude"' not in user_prompt
    assert '"elevation_change_m"' not in user_prompt
    assert "recorded Garmin laps" in system_prompt


def test_ride_context_uses_recorded_speed_and_missing_splits_have_no_stream_fallback():
    repository = RepositoryStub()
    repository.current.sport_type = "Ride"
    context = CoachingContextBuilder(repository).build_activity_context(user_id=1, activity_id=10)
    assert context["splits"][1]["speed_kph"] == 14.4
    assert "pace" not in context["splits"][1]
    repository.get_splits = lambda _id: SimpleNamespace(status="unavailable", laps=[])
    context = CoachingContextBuilder(repository).build_activity_context(user_id=1, activity_id=10)
    assert "splits" not in context
    assert "split_data_limitation" in context
    assert "streams" not in context


def test_period_context_flags_pending_notes_and_hashes_its_inputs() -> None:
    repository = RepositoryStub()
    builder = CoachingContextBuilder(repository)

    in_progress = builder.build_period_context(
        user_id=1, period_type="week", period_start=date(2026, 10, 5), today=date(2026, 10, 8)
    )
    assert in_progress.context["in_progress"] is True
    assert in_progress.context["period_end"] == "2026-10-11"
    assert in_progress.is_final is False
    assert in_progress.has_pending_notes is True
    assert in_progress.has_ready_notes is True
    assert in_progress.context["totals_by_sport"]["Run"]["activities"] == 2
    assert in_progress.context["previous_period_totals_by_sport"] == {}
    assert [item.get("coaching_summary") for item in in_progress.context["activities"]] == [
        "Easy recovery run.",
        None,
    ]

    repository.notes[10] = SimpleNamespace(status="ready", summary="Fast 10 km.")
    finished = builder.build_period_context(
        user_id=1, period_type="week", period_start=date(2026, 10, 5), today=date(2026, 10, 12)
    )
    assert finished.is_final is True
    assert finished.has_pending_notes is False
    assert finished.source_hash != in_progress.source_hash

    same_inputs = builder.build_period_context(
        user_id=1, period_type="week", period_start=date(2026, 10, 5), today=date(2026, 10, 20)
    )
    assert same_inputs.source_hash == finished.source_hash

    system_prompt, _ = build_period_prompt(finished.context)
    assert "one training week" in system_prompt
    assert "next week" in system_prompt
    system_prompt, _ = build_period_prompt({**in_progress.context, "period_type": "month"})
    assert "rest of the month" in system_prompt


def test_period_helpers() -> None:
    assert period_start_for("week", date(2026, 10, 11)) == date(2026, 10, 5)
    assert period_start_for("month", date(2026, 10, 11)) == date(2026, 10, 1)
    assert period_bounds("month", date(2026, 12, 1)) == (date(2026, 12, 1), date(2027, 1, 1))
    assert previous_period_start("month", date(2026, 3, 1)) == date(2026, 2, 1)
    assert previous_period_start("week", date(2026, 10, 5)) == date(2026, 10, 5) - timedelta(days=7)


def test_parsers_require_every_text_field() -> None:
    narrative = parse_activity_narrative(
        {"description": [" First. ", "Second."], "summary": " Short. ", "recommendation": "Rest."}
    )
    assert narrative.description == "First.\n\nSecond."
    assert narrative.summary == "Short."
    assert parse_period_review({"summary": "Week.", "recommendation": "More."}).recommendation == "More."
    with pytest.raises(LlmResponseFormatError):
        parse_activity_narrative({"description": "x", "summary": "", "recommendation": "y"})
    with pytest.raises(LlmResponseFormatError):
        parse_period_review({"summary": "Week."})


def test_equal_elapsed_and_moving_time_is_omitted_but_athlete_notes_remain():
    repository = RepositoryStub()
    repository.current.elapsed_time_seconds = repository.current.moving_time_seconds
    repository.current.description = "Easy run after poor sleep."
    context = CoachingContextBuilder(repository).build_activity_context(user_id=1, activity_id=10)
    assert "elapsed_time" not in context["activity"]
    assert context["activity"]["athlete_notes"] == "Easy run after poor sleep."
