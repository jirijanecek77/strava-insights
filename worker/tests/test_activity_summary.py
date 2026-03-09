from datetime import UTC, date, datetime
from decimal import Decimal

from app.services.activity_summary import (
    difficulty_score,
    distance_km,
    format_moving_time,
    format_pace,
    max_bpm_for_profile,
    pace_seconds_per_km,
    speed_kph,
    summary_metric_display,
)


def test_activity_summary_helpers_compute_normalized_values() -> None:
    assert distance_km(Decimal("10000")) == Decimal("10.00")
    assert format_moving_time(2700) == "45:00"
    assert speed_kph(Decimal("3.7")) == Decimal("13.32")
    assert pace_seconds_per_km(Decimal("10000"), 2700, "Run") == Decimal("270.00")
    assert format_pace(Decimal("270.00")) == "4:30"
    assert summary_metric_display("Run", pace_display="4:30", speed_kph_value=Decimal("13.32")) == "4:30 /km"
    assert summary_metric_display("Ride", pace_display=None, speed_kph_value=Decimal("31.50")) == "31.50 km/h"


def test_difficulty_score_uses_profile_speed_and_max_bpm() -> None:
    max_bpm = max_bpm_for_profile(
        birthday=date(1990, 1, 1),
        activity_date=datetime(2026, 3, 9, tzinfo=UTC),
        max_heart_rate_override=None,
    )

    score = difficulty_score(
        distance_km_value=Decimal("10.00"),
        total_elevation_gain_meters=Decimal("100.00"),
        average_heartrate_bpm=Decimal("150.00"),
        average_speed_kph_value=Decimal("13.32"),
        speed_max=Decimal("15.50"),
        max_bpm=max_bpm,
    )

    assert max_bpm == Decimal("194.80")
    assert score is not None
