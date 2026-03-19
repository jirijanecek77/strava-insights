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


