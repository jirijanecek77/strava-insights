from decimal import Decimal

from app.services.activity_summary import distance_km, format_moving_time, format_pace, pace_seconds_per_km, speed_kph, summary_metric_display


def test_activity_summary_helpers_compute_normalized_values() -> None:
    assert distance_km(Decimal("10000")) == Decimal("10.00")
    assert format_moving_time(2700) == "45:00"
    assert speed_kph(Decimal("3.7")) == Decimal("13.32")
    assert pace_seconds_per_km(Decimal("10000"), 2700, "Run") == Decimal("270.00")
    assert format_pace(Decimal("270.00")) == "4:30"
    assert summary_metric_display("Run", pace_display="4:30", speed_kph_value=Decimal("13.32")) == "4:30 /km"
    assert summary_metric_display("Ride", pace_display=None, speed_kph_value=Decimal("31.50")) == "31.50 km/h"
