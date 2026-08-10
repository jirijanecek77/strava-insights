from datetime import date
from decimal import Decimal

from app.application.analytics.aggregations import (
    ActivityAggregateInput,
    PeriodSummaryResult,
    compare_periods,
    summarize_window,
)


def test_compare_periods_returns_numeric_deltas() -> None:
    previous = PeriodSummaryResult(
        "Run",
        "month",
        date(2026, 2, 1),
        1,
        Decimal("8000"),
        2400,
        None,
        Decimal("300"),
        Decimal("50"),
    )
    current = PeriodSummaryResult(
        "Run",
        "month",
        date(2026, 3, 1),
        1,
        Decimal("10000"),
        2700,
        None,
        Decimal("270"),
        Decimal("100"),
    )
    comparison = compare_periods(current=current, previous=previous)

    assert comparison["delta_distance_meters"] is not None


def test_summarize_window_builds_rolling_period_metrics() -> None:
    summary = summarize_window(
        [
            ActivityAggregateInput(
                "Run", date(2026, 3, 1), Decimal("10000"), 2700, Decimal("100")
            ),
            ActivityAggregateInput(
                "Run", date(2026, 3, 2), Decimal("5000"), 1500, Decimal("50")
            ),
        ],
        sport_type="Run",
        window_type="rolling_30d",
        window_start=date(2026, 2, 9),
    )

    assert summary is not None
    assert summary.average_pace_seconds_per_km == Decimal("280.00")
