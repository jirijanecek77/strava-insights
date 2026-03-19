from datetime import datetime

from app.application.analytics.detail_series import (
    calculate_pace_minutes_per_km,
    calculate_slope_percent,
    format_pace_minutes_per_km,
    meters_to_kilometers,
    moving_average_heartrate,
    moving_average_speed_kph,
)
from app.application.analytics.cycling_analysis import build_cycling_analysis
from app.application.analytics.heart_rate_drift import calculate_heart_rate_drift_bpm
from app.application.analytics.running_analysis import build_running_analysis


class ActivityDetailAnalyticsService:
    def build(
        self,
        *,
        sport_type: str,
        start_date_utc: datetime | None,
        time_stream: list[int] | None,
        distance_stream_meters: list[float] | None,
        heartrate_stream_bpm: list[float] | None,
        altitude_stream_meters: list[float] | None,
        velocity_smooth_stream_mps: list[float] | None,
        average_cadence: float | None,
        aet_heart_rate_bpm: int | None,
        ant_heart_rate_bpm: int | None,
        aet_pace_min_per_km: float | None,
        ant_pace_min_per_km: float | None,
    ) -> dict:
        distance_km = meters_to_kilometers(distance_stream_meters or []) if distance_stream_meters else []
        heartrate_ma = (
            moving_average_heartrate(heartrate_stream_bpm or [], range_points=10) if heartrate_stream_bpm else []
        )
        speed_ma_kph = (
            moving_average_speed_kph(velocity_smooth_stream_mps or [], range_points=10)
            if velocity_smooth_stream_mps
            else []
        )
        pace_minutes_per_km = (
            calculate_pace_minutes_per_km(time_stream or [], distance_stream_meters or [], range_points=20)
            if sport_type == "Run" and time_stream and distance_stream_meters
            else []
        )
        pace_display = format_pace_minutes_per_km(pace_minutes_per_km) if pace_minutes_per_km else []
        slope_percent = (
            calculate_slope_percent(altitude_stream_meters or [], distance_stream_meters or [], range_points=30)
            if altitude_stream_meters and distance_stream_meters
            else []
        )

        heart_rate_drift_bpm = calculate_heart_rate_drift_bpm(
            distance_stream_meters=distance_stream_meters,
            heartrate_stream_bpm=heartrate_stream_bpm,
        )
        result = {
            "distance_km": distance_km,
            "altitude_meters": altitude_stream_meters or [],
            "moving_average_heartrate": heartrate_ma,
            "heart_rate_drift_bpm": heart_rate_drift_bpm,
            "moving_average_speed_kph": speed_ma_kph,
            "pace_minutes_per_km": pace_minutes_per_km,
            "pace_display": pace_display,
            "slope_percent": slope_percent,
            "running_analysis": None,
            "cycling_analysis": None,
        }

        if sport_type in {"Ride", "EBikeRide"} and speed_ma_kph:
            result["cycling_analysis"] = build_cycling_analysis(
                distance_km=distance_km,
                speed_kph=speed_ma_kph,
                slope_percent=slope_percent,
                heart_rate_bpm=heartrate_ma,
                average_cadence=average_cadence,
                heart_rate_drift_bpm=float(heart_rate_drift_bpm) if heart_rate_drift_bpm is not None else None,
                aet_heart_rate_bpm=float(aet_heart_rate_bpm) if aet_heart_rate_bpm is not None else None,
                ant_heart_rate_bpm=float(ant_heart_rate_bpm) if ant_heart_rate_bpm is not None else None,
            )

        if (
            sport_type != "Run"
            or not pace_minutes_per_km
            or not heartrate_ma
            or aet_heart_rate_bpm is None
            or ant_heart_rate_bpm is None
            or aet_pace_min_per_km is None
            or ant_pace_min_per_km is None
        ):
            return result

        result["running_analysis"] = build_running_analysis(
            distance_km=distance_km,
            pace_minutes_per_km=pace_minutes_per_km,
            heart_rate_bpm=heartrate_ma,
            aet_pace_min_per_km=float(aet_pace_min_per_km),
            ant_pace_min_per_km=float(ant_pace_min_per_km),
            aet_heart_rate_bpm=float(aet_heart_rate_bpm),
            ant_heart_rate_bpm=float(ant_heart_rate_bpm),
        )
        return result
