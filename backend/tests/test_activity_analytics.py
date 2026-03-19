from datetime import UTC, datetime
from decimal import Decimal

from app.application.analytics.detail_series import (
    calculate_pace_minutes_per_km,
    calculate_slope_percent,
    format_pace_minutes_per_km,
    moving_average,
    moving_average_speed_kph,
)
from app.application.analytics.heart_rate_drift import calculate_heart_rate_drift_bpm
from app.application.analytics.running_analysis import build_running_analysis
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


def test_running_analysis_builds_threshold_distributions_and_agreement() -> None:
    analysis = build_running_analysis(
        distance_km=[0.0, 1.0, 2.0, 3.0, 4.0],
        pace_minutes_per_km=[6.2, 6.0, 5.2, 4.9, 4.3],
        heart_rate_bpm=[138, 140, 151, 159, 171],
        aet_pace_min_per_km=5.8,
        ant_pace_min_per_km=4.8,
        aet_heart_rate_bpm=145,
        ant_heart_rate_bpm=165,
    )

    assert analysis is not None
    assert analysis["pace_distribution"][0]["code"] == "below_aet"
    assert analysis["pace_distribution"][1]["distance_km"] == 2.0
    assert analysis["heart_rate_distribution"][2]["distance_km"] == 1.0
    assert analysis["agreement"]["matching_distance_km"] == 4.0
    assert analysis["steady_threshold_block"]["distance_km"] == 2.0
    assert analysis["above_threshold_block"]["distance_km"] == 1.0
    assert analysis["activity_evaluation"]
    assert analysis["further_training_suggestion"]


def test_activity_detail_service_builds_threshold_running_analysis() -> None:
    service = ActivityDetailAnalyticsService()

    payload = service.build(
        sport_type="Run",
        start_date_utc=datetime(2026, 3, 9, 6, 0, tzinfo=UTC),
        time_stream=[0, 60, 120, 180, 240, 300],
        distance_stream_meters=[0, 250, 500, 750, 1000, 1250],
        heartrate_stream_bpm=[150, 151, 152, 153, 154, 155],
        altitude_stream_meters=[200, 201, 202, 203, 204, 205],
        velocity_smooth_stream_mps=[4.0, 4.1, 4.2, 4.3, 4.4, 4.5],
        aet_heart_rate_bpm=148,
        ant_heart_rate_bpm=158,
        aet_pace_min_per_km=4.8,
        ant_pace_min_per_km=4.1,
    )

    assert payload["pace_display"][0] == "4:00"
    assert payload["heart_rate_drift_bpm"] == Decimal("3.00")
    assert payload["running_analysis"] is not None
    assert payload["running_analysis"]["agreement"]["matching_distance_km"] >= 0
    assert payload["running_analysis"]["activity_evaluation"]
    assert payload["running_analysis"]["further_training_suggestion"]


def test_activity_detail_service_omits_running_analysis_without_complete_thresholds() -> None:
    service = ActivityDetailAnalyticsService()

    payload = service.build(
        sport_type="Run",
        start_date_utc=datetime(2026, 3, 9, 6, 0, tzinfo=UTC),
        time_stream=[0, 60, 120, 180],
        distance_stream_meters=[0, 250, 500, 750],
        heartrate_stream_bpm=[150, 151, 152, 153],
        altitude_stream_meters=[200, 201, 202, 203],
        velocity_smooth_stream_mps=[4.0, 4.1, 4.2, 4.3],
        aet_heart_rate_bpm=148,
        ant_heart_rate_bpm=None,
        aet_pace_min_per_km=4.8,
        ant_pace_min_per_km=4.1,
    )

    assert payload["running_analysis"] is None


def test_heart_rate_drift_uses_first_and_second_half_averages() -> None:
    drift = calculate_heart_rate_drift_bpm(
        distance_stream_meters=[0, 250, 750, 1250],
        heartrate_stream_bpm=[145, 146, 150, 152],
    )
    assert drift == Decimal("5.00")
