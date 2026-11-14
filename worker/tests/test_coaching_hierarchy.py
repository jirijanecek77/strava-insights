"""Regression coverage for the activity -> week -> calendar-month handoff."""

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from test_coaching_context_builder import RepositoryStub

from app.services.coaching.context_builder import CoachingContextBuilder


def saved_activity(
        activity_id, day, seconds=(1800, 600, 0), summary="Steady aerobic work."
):
    bands = {
        band: {"time_s": time, "distance_m": time * 3}
        for band, time in zip(("below_aet", "between_aet_ant", "above_ant"), seconds)
    }
    return {
        "status": "ready",
        "summary": summary,
        "revision": f"activity-{activity_id}-v1",
        "facts": {
            "activity_id": activity_id,
            "date": day,
            "sport": "Run",
            "route_group_id": None,
            "threshold_snapshot": None,
            "volume": {"distance_m": sum(seconds) * 3, "moving_time_s": sum(seconds)},
            "hr_bands": {
                "bands": bands,
                "coverage": {
                    "classified_time_s": sum(seconds),
                    "classified_distance_m": sum(seconds) * 3,
                    "unknown_time_s": 0,
                    "unknown_distance_m": 0,
                },
                "limitations": [],
            },
            "candidates": {"endurance": [], "tempo": []},
        },
    }


class SavedRepository:
    def __init__(self):
        self.activities = []
        self.periods = []

    def list_activity_evaluations(self, *, user_id, start, end):
        return [
            row
            for row in self.activities
            if str(start) <= row["facts"]["date"] < str(end)
        ]

    def list_period_evaluations(self, *, user_id, period_type, start, end):
        return [
            row
            for row in self.periods
            if row.period_type == period_type and start <= row.period_start < end
        ]

    def list_activities_with_notes(self, **kwargs):
        raise AssertionError(
            "Period reviews must read saved evaluations, never original activities"
        )

    def get_stream(self, *args):
        raise AssertionError("Period reviews must never read streams")

    def activity_evidence_batch(self, **kwargs):
        raise AssertionError("Period reviews must not recalculate activity evidence")


def build_week(repository, start, today=date(2026, 12, 1)):
    result = CoachingContextBuilder(repository).build_period_context(
        user_id=1,
        period_type="week",
        period_start=start,
        today=today,
    )
    return SimpleNamespace(
        period_type="week",
        period_start=start,
        status="ready",
        summary=f"Week starting {start}.",
        recommendation="Keep training.",
        source_hash=result.source_hash,
        metrics=result.metrics,
        is_final=result.is_final,
        generated_at=None,
    )


def test_week_reuses_activity_evaluations_and_weights_zone_percentages_by_time():
    repository = SavedRepository()
    repository.activities = [
        saved_activity(1, "2026-11-03", (3600, 0, 0)),
        saved_activity(2, "2026-11-04", (0, 1200, 0)),
    ]
    result = CoachingContextBuilder(repository).build_period_context(
        user_id=1,
        period_type="week",
        period_start=date(2026, 11, 2),
        today=date(2026, 11, 9),
    )
    bands = result.context["hr_bands_by_sport"]["Run"]["bands"]
    assert bands["below_aet"]["time_percent"] == 75
    assert bands["between_aet_ant"]["time_percent"] == 25
    assert len(result.context["activities"]) == 2
    assert "splits" not in str(result.context)
    assert result.metrics["hierarchy"]["days"]


def test_calendar_month_uses_only_saved_weeks_and_clips_both_boundary_weeks():
    repository = SavedRepository()
    repository.activities = [
        saved_activity(1, "2026-10-31", (900, 0, 0)),
        saved_activity(2, "2026-11-01", (1200, 0, 0)),
        saved_activity(3, "2026-11-30", (1800, 0, 0)),
        saved_activity(4, "2026-12-01", (600, 0, 0)),
    ]
    repository.periods = [
        build_week(repository, date(2026, 10, 26), today=date(2026, 12, 2)),
        build_week(repository, date(2026, 11, 30), today=date(2026, 12, 2)),
    ]
    repository.list_activity_evaluations = lambda **kwargs: pytest.fail(
        "A month must not read activity evaluations"
    )
    builder = CoachingContextBuilder(repository)
    result = builder.build_period_context(
        user_id=1,
        period_type="month",
        period_start=date(2026, 11, 1),
        today=date(2026, 12, 2),
    )
    assert result.is_final
    assert result.context["date_coverage"]["covered_days"] == 2
    assert result.context["rest_days"] is None
    assert result.context["totals_by_sport"]["Run"]["activities"] == 2
    assert (
            result.context["hr_bands_by_sport"]["Run"]["bands"]["below_aet"]["time_s"]
            == 3000
    )
    assert "activities" not in result.context
    assert len(result.context["weeks"]) == 2
    original = result.source_hash
    repository.periods[1].summary = "An updated assessment of the long run."
    assert (
            builder.build_period_context(
                user_id=1,
                period_type="month",
                period_start=date(2026, 11, 1),
                today=date(2026, 12, 2),
            ).source_hash
            != original
    )


def test_activity_does_not_send_unqualified_whole_session_decoupling():
    context = CoachingContextBuilder(RepositoryStub()).build_activity_context(
        user_id=1, activity_id=10
    )
    assert "aerobic_decoupling_percent" not in context


def test_month_to_date_comparison_clips_previous_week_at_the_same_day():
    repository = SavedRepository()
    repository.activities = [
        saved_activity(i, day)
        for i, day in enumerate(
            ("2026-10-13", "2026-10-14", "2026-10-15", "2026-11-14"), start=1
        )
    ]
    repository.periods = [
        build_week(repository, day) for day in (date(2026, 10, 12), date(2026, 11, 9))
    ]
    result = CoachingContextBuilder(repository).build_period_context(
        user_id=1,
        period_type="month",
        period_start=date(2026, 11, 1),
        today=date(2026, 11, 14),
    )
    assert result.context["previous_period_totals_by_sport"]["Run"]["activities"] == 2
    assert (
            result.context["previous_full_period_totals_by_sport"]["Run"]["activities"] == 3
    )


def test_three_previous_same_level_reviews_are_context_not_current_volume():
    repository = SavedRepository()
    repository.activities = [saved_activity(1, "2026-11-03")]
    week = build_week(repository, date(2026, 11, 2))
    repository.periods = [week] + [
        SimpleNamespace(
            period_type="month",
            period_start=date(2026, month, 1),
            status="ready",
            summary=f"Review {month}.",
            metrics={"totals_by_sport": {"Run": {"activities": 100}}},
        )
        for month in (7, 8, 9, 10)
    ]
    result = CoachingContextBuilder(repository).build_period_context(
        user_id=1,
        period_type="month",
        period_start=date(2026, 11, 1),
        today=date(2026, 12, 1),
    )
    assert [row["period_start"] for row in result.context["previous_reviews"]] == [
        "2026-08-01",
        "2026-09-01",
        "2026-10-01",
    ]
    assert result.context["totals_by_sport"]["Run"]["activities"] == 1


def test_monthly_endurance_evidence_survives_weekly_handoffs_without_activity_reads():
    import json

    from app.services.coaching.prompts import build_period_prompt

    repository = SavedRepository()
    starts = (
        date(2026, 10, 12),
        date(2026, 10, 19),
        date(2026, 11, 2),
        date(2026, 11, 9),
    )
    for activity_id, day in enumerate(starts, start=1):
        row = saved_activity(activity_id, str(day))
        pace = 350 if day.month == 10 else 330
        row["facts"]["threshold_snapshot"] = {
            "aet_hr_bpm": 140,
            "ant_hr_bpm": 165,
            "effective_from": "2026-01-01",
        }
        row["facts"]["candidates"]["endurance"] = [
            {
                "lap_range": [1, 6],
                "duration_s": 1800,
                "distance_m": 1800000 / pace,
                "pace_s_per_km": pace,
                "hr_bpm": 130,
                "net_grade_pct": 0,
                "ascent_m_per_km": 0,
                "efficiency_m_per_beat": 60000 / pace / 130,
            }
        ]
        repository.activities.append(row)
    repository.periods = [build_week(repository, start) for start in starts]
    repository.list_activity_evaluations = lambda **kwargs: pytest.fail(
        "Month must use saved weeks"
    )
    result = CoachingContextBuilder(repository).build_period_context(
        user_id=1,
        period_type="month",
        period_start=date(2026, 11, 1),
        today=date(2026, 12, 1),
    )
    comparison = result.context["performance_comparison"]["endurance"]
    assert comparison["matched_pairs"] == 2
    assert comparison["status"] == "improving"
    assert comparison["median_pace_change_pct"] == pytest.approx(-100 * 20 / 350)
    _, prompt = build_period_prompt(result.context)
    sent = json.loads(prompt.split("\n", 1)[1])
    assert "activities" not in sent and "hierarchy" not in sent
    assert (
            sent["performance_comparison"]["endurance"]["evidence"][0]["current"][
                "efficiency_m_per_beat"
            ]
            > 1
    )
    assert "lap_range" not in prompt and "start_distance_m" not in prompt


def test_reprepared_facts_do_not_mix_with_the_previous_successful_activity_summary():
    from unittest.mock import Mock

    from app.repositories import CoachingRepository

    stored = SimpleNamespace(
        facts=saved_activity(1, "2026-11-03")["facts"], source_hash="original"
    )
    session = Mock()
    session.get.return_value = stored
    repository = CoachingRepository(session)
    note = SimpleNamespace(activity_id=1, status="pending")
    repository.mark_activity_note_ready(
        note,
        description="Steady work.",
        summary="Aerobic stimulus.",
        recommendation="Recover.",
        model="test",
        prompt_version="5",
    )
    stored.facts = {
        **stored.facts,
        "volume": {"distance_m": 8000, "moving_time_s": 2600},
    }
    stored.source_hash = "reprepared"
    note.status = "pending"
    reused = repository._activity_evaluation(None, note, stored)
    assert reused.facts.volume.distance_m == 7200
    assert reused.summary == "Aerobic stimulus."
    assert reused.status == "pending"
    repository.mark_activity_note_ready(
        note,
        description="Changed work.",
        summary="Updated stimulus.",
        recommendation="Easy run.",
        model="test",
        prompt_version="5",
    )
    replaced = repository._activity_evaluation(None, note, stored)
    assert replaced.facts.volume.distance_m == 8000
    assert replaced.summary == "Updated stimulus."
