from datetime import UTC, date, datetime
from decimal import Decimal

from app.application.analytics.detail_series import (
    calculate_pace_minutes_per_km,
    calculate_slope_percent,
    format_pace_minutes_per_km,
    moving_average,
    moving_average_speed_kph,
)
from app.application.analytics.difficulty import calculate_activity_difficulty
from app.application.analytics.heart_rate_drift import calculate_heart_rate_drift_bpm
from app.application.analytics.running_zones import build_running_zones, resolve_running_zone
from app.application.analytics.service import ActivityDetailAnalyticsService


def test_detail_series_match_legacy_formulas() -> None:
    assert moving_average([1, 2, 3, 4, 5], range_points=1) == [1.5, 2.0, 3.0, 4.0, 4.5]
    assert moving_average_speed_kph([1.0, 2.0, 3.0], range_points=1) == [5.4, 7.2, 9.0]
    paces = calculate_pace_minutes_per_km([0, 60, 120, 180], [0, 250, 500, 750], range_points=1)
    assert paces == [4.0, 4.0, 4.0, 4.0]
    assert format_pace_minutes_per_km([4.0, float("inf")]) == ["4:00", "0:00"]


def test_slope_is_clamped_and_padded_like_legacy_code() -> None:
    slopes = calculate_slope_percent(
        altitude_stream_meters=[0, 10, 20, 30, 1000],
        distance_stream_meters=[0, 1, 2, 3, 4],
        range_points=2,
    )
    assert slopes[0] == 0.0
    assert max(slopes) == 45.0


def test_running_zone_model_uses_midpoint_boundaries() -> None:
    zones = build_running_zones(age=30, speed_max=15.0)
    marathon_zone = next(zone for zone in zones if zone.name == "Marathon")
    assert round(marathon_zone.pace, 2) == round(60 / (0.75 * 15.0), 2)
    resolved = resolve_running_zone(zones, pace=marathon_zone.pace, heart_rate=marathon_zone.bpm)
    assert resolved == {"zone_pace": "Marathon", "zone_heart_rate": "Marathon"}


def test_activity_detail_service_builds_running_intervals_and_compliance() -> None:
    service = ActivityDetailAnalyticsService()

    payload = service.build(
        sport_type="Run",
        start_date_utc=datetime(2026, 3, 9, 6, 0, tzinfo=UTC),
        time_stream=[0, 60, 120, 180, 240, 300],
        distance_stream_meters=[0, 250, 500, 750, 1000, 1250],
        heartrate_stream_bpm=[150, 151, 152, 153, 154, 155],
        altitude_stream_meters=[200, 201, 202, 203, 204, 205],
        velocity_smooth_stream_mps=[4.0, 4.1, 4.2, 4.3, 4.4, 4.5],
        birthday=date(1990, 1, 1),
        speed_max=Decimal("15.50"),
    )

    assert payload["pace_display"][0] == "4:00"
    assert payload["heart_rate_drift_bpm"] == Decimal("3.00")
    assert payload["zones"]
    assert payload["intervals"]
    assert payload["zone_summary"]
    assert payload["compliance"] is not None


def test_activity_difficulty_matches_spec_formula() -> None:
    difficulty = calculate_activity_difficulty(
        distance_km=Decimal("10.00"),
        total_elevation_gain_meters=Decimal("100.00"),
        average_heartrate_bpm=Decimal("150.00"),
        average_speed_kph=Decimal("13.32"),
        user_speed_max=Decimal("15.50"),
        user_max_bpm=Decimal("194.80"),
    )
    assert difficulty is not None


def test_heart_rate_drift_uses_first_and_second_half_averages() -> None:
    drift = calculate_heart_rate_drift_bpm(
        distance_stream_meters=[0, 250, 750, 1250],
        heartrate_stream_bpm=[145, 146, 150, 152],
    )
    assert drift == Decimal("5.00")
