from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP


def _quantize(value: Decimal, precision: str) -> Decimal:
    return value.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


def distance_km(distance_meters: Decimal) -> Decimal:
    return _quantize(distance_meters / Decimal("1000"), "0.01")


def format_moving_time(moving_time_seconds: int) -> str:
    hours, remainder = divmod(moving_time_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def speed_kph(average_speed_mps: Decimal | None) -> Decimal | None:
    if average_speed_mps is None:
        return None
    return _quantize(average_speed_mps * Decimal("3.6"), "0.01")


def pace_seconds_per_km(distance_meters: Decimal, moving_time_seconds: int, sport_type: str) -> Decimal | None:
    if sport_type != "Run" or distance_meters <= 0:
        return None
    return _quantize((Decimal(moving_time_seconds) * Decimal("1000")) / distance_meters, "0.01")


def format_pace(pace_seconds_per_km_value: Decimal | None) -> str | None:
    if pace_seconds_per_km_value is None:
        return None
    total_seconds = int(pace_seconds_per_km_value.to_integral_value(rounding=ROUND_HALF_UP))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}:{seconds:02d}"


def summary_metric_display(sport_type: str, *, pace_display: str | None, speed_kph_value: Decimal | None) -> str | None:
    if sport_type == "Run":
        return None if pace_display is None else f"{pace_display} /km"
    if speed_kph_value is None:
        return None
    return f"{speed_kph_value} km/h"


def max_bpm_for_profile(*, birthday: date | None, activity_date: datetime | None, max_heart_rate_override: int | None) -> Decimal | None:
    if max_heart_rate_override is not None:
        return Decimal(max_heart_rate_override)
    if birthday is None or activity_date is None:
        return None
    reference_date = activity_date.astimezone(UTC).date()
    age = reference_date.year - birthday.year - ((reference_date.month, reference_date.day) < (birthday.month, birthday.day))
    return _quantize(Decimal("220") - (Decimal("0.7") * Decimal(age)), "0.01")


def difficulty_score(
    *,
    distance_km_value: Decimal,
    total_elevation_gain_meters: Decimal | None,
    average_heartrate_bpm: Decimal | None,
    average_speed_kph_value: Decimal | None,
    speed_max: Decimal | None,
    max_bpm: Decimal | None,
) -> Decimal | None:
    if (
        total_elevation_gain_meters is None
        or average_heartrate_bpm is None
        or average_speed_kph_value is None
        or speed_max is None
        or max_bpm is None
        or max_bpm == 0
    ):
        return None
    d_distance_km = distance_km_value / Decimal("15")
    d_total_elevation_gain = total_elevation_gain_meters / Decimal("150")
    d_average_heartrate = average_heartrate_bpm / max_bpm
    d_average_speed = Decimal("6") - abs(speed_max - average_speed_kph_value)
    return _quantize(
        d_distance_km * d_total_elevation_gain * d_average_heartrate * d_average_speed,
        "0.0001",
    )
