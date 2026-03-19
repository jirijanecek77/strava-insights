from datetime import date, datetime, UTC
from decimal import Decimal

from app.application.analytics.aggregations import ActivityAggregateInput, aggregate_period_summaries, compare_periods, summarize_window
from app.application.analytics.best_efforts import derive_activity_best_efforts


def test_aggregate_period_summaries_uses_weighted_period_metrics() -> None:
    activities = [
        ActivityAggregateInput(
            sport_type="Run",
            start_date_local=date(2026, 3, 1),
            distance_meters=Decimal("10000"),
            moving_time_seconds=2700,
            total_elevation_gain_meters=Decimal("100"),
            heart_rate_drift_bpm=Decimal("3.00"),
        ),
        ActivityAggregateInput(
            sport_type="Run",
            start_date_local=date(2026, 3, 2),
            distance_meters=Decimal("5000"),
            moving_time_seconds=1500,
            total_elevation_gain_meters=Decimal("50"),
            heart_rate_drift_bpm=Decimal("5.00"),
        ),
    ]

    summaries = aggregate_period_summaries(activities, period_type="month")

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.total_distance_meters == Decimal("15000.00")
    assert summary.total_moving_time_seconds == 4200
    assert summary.average_pace_seconds_per_km == Decimal("280.00")
    assert summary.average_heart_rate_drift_bpm == Decimal("4.00")


def test_aggregate_period_summaries_supports_week_period() -> None:
    activities = [
        ActivityAggregateInput(
            sport_type="Run",
            start_date_local=date(2026, 3, 10),
            distance_meters=Decimal("10000"),
            moving_time_seconds=2700,
            total_elevation_gain_meters=Decimal("100"),
            heart_rate_drift_bpm=Decimal("3.00"),
        )
    ]

    summaries = aggregate_period_summaries(activities, period_type="week")

    assert summaries[0].period_start == date(2026, 3, 9)


def test_compare_periods_returns_numeric_deltas() -> None:
    summaries = aggregate_period_summaries(
        [
            ActivityAggregateInput("Run", date(2026, 3, 1), Decimal("10000"), 2700, Decimal("100"), Decimal("3.0")),
            ActivityAggregateInput("Run", date(2026, 2, 1), Decimal("8000"), 2400, Decimal("50"), Decimal("2.0")),
        ],
        period_type="month",
    )
    comparison = compare_periods(current=summaries[1], previous=summaries[0])

    assert comparison["delta_distance_meters"] is not None


def test_derive_activity_best_efforts_finds_shortest_segment_times() -> None:
    efforts = derive_activity_best_efforts(
        activity_id=12,
        achieved_at=datetime(2026, 3, 9, tzinfo=UTC),
        distance_stream_meters=[0, 500, 1000, 2000, 5000, 10000, 21097.5],
        time_stream_seconds=[0, 120, 240, 500, 1400, 3000, 7000],
    )

    by_code = {effort.effort_code: effort for effort in efforts}
    assert by_code["1km"].best_time_seconds == 240
    assert by_code["5km"].best_time_seconds == 1400
    assert by_code["10km"].best_time_seconds == 3000
    assert by_code["Half-Marathon"].best_time_seconds == 7000


def test_summarize_window_builds_rolling_period_metrics() -> None:
    summary = summarize_window(
        [
            ActivityAggregateInput("Run", date(2026, 3, 1), Decimal("10000"), 2700, Decimal("100"), Decimal("3.0")),
            ActivityAggregateInput("Run", date(2026, 3, 2), Decimal("5000"), 1500, Decimal("50"), Decimal("5.0")),
        ],
        sport_type="Run",
        window_type="rolling_30d",
        window_start=date(2026, 2, 9),
    )

    assert summary is not None
    assert summary.average_pace_seconds_per_km == Decimal("280.00")
    assert summary.average_heart_rate_drift_bpm == Decimal("4.00")
