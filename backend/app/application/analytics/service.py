from datetime import date, datetime, UTC
from decimal import Decimal

from app.application.analytics.detail_series import (
    calculate_pace_minutes_per_km,
    calculate_slope_percent,
    format_pace_minutes_per_km,
    meters_to_kilometers,
    moving_average_heartrate,
    moving_average_speed_kph,
)
from app.application.analytics.heart_rate_drift import calculate_heart_rate_drift_bpm
from app.application.analytics.interval_analysis import (
    build_running_compliance,
    group_running_intervals,
    summarize_running_intervals,
)
from app.application.analytics.running_zones import bpm_max_for_age, build_running_zones


def _calculate_age(birthday: date, reference_date: date) -> int:
    return reference_date.year - birthday.year - (
        (reference_date.month, reference_date.day) < (birthday.month, birthday.day)
    )


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
        birthday: date | None,
        speed_max: Decimal | None,
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

        result = {
            "distance_km": distance_km,
            "altitude_meters": altitude_stream_meters or [],
            "moving_average_heartrate": heartrate_ma,
            "heart_rate_drift_bpm": calculate_heart_rate_drift_bpm(
                distance_stream_meters=distance_stream_meters,
                heartrate_stream_bpm=heartrate_stream_bpm,
            ),
            "moving_average_speed_kph": speed_ma_kph,
            "pace_minutes_per_km": pace_minutes_per_km,
            "pace_display": pace_display,
            "slope_percent": slope_percent,
            "intervals": [],
            "zone_summary": {},
            "compliance": None,
            "zones": [],
        }

        if sport_type != "Run" or not pace_minutes_per_km or not heartrate_ma or birthday is None or speed_max is None:
            return result

        reference_date = (start_date_utc or datetime.now(UTC)).date()
        age = _calculate_age(birthday, reference_date)
        zones = build_running_zones(age=age, speed_max=float(speed_max))
        intervals = group_running_intervals(
            distance_km=distance_km,
            paces=pace_minutes_per_km,
            heart_rates=heartrate_ma,
            zones=zones,
        )
        zone_summary = summarize_running_intervals(intervals)
        compliance = build_running_compliance(zone_summary, activity_distance_km=max(distance_km) if distance_km else 0.0)

        result["zones"] = [
            {
                "name": zone.name,
                "pace": zone.pace,
                "bpm": zone.bpm,
                "color": zone.color,
                "range_zone_pace": {"lower": zone.range_zone_pace.lower, "upper": zone.range_zone_pace.upper},
                "range_zone_bpm": {"lower": zone.range_zone_bpm.lower, "upper": zone.range_zone_bpm.upper},
            }
            for zone in zones
        ]
        result["intervals"] = intervals
        result["zone_summary"] = zone_summary
        result["compliance"] = compliance
        result["bpm_max"] = bpm_max_for_age(age)
        return result
