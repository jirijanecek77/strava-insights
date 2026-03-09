from decimal import Decimal, ROUND_HALF_UP


def _quantize(value: Decimal, precision: str) -> Decimal:
    return value.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


def calculate_activity_difficulty(
    *,
    distance_km: Decimal,
    total_elevation_gain_meters: Decimal | None,
    average_heartrate_bpm: Decimal | None,
    average_speed_kph: Decimal | None,
    user_speed_max: Decimal | None,
    user_max_bpm: Decimal | None,
) -> Decimal | None:
    if (
        total_elevation_gain_meters is None
        or average_heartrate_bpm is None
        or average_speed_kph is None
        or user_speed_max is None
        or user_max_bpm is None
        or user_max_bpm == 0
    ):
        return None
    d_distance_km = distance_km / Decimal("15")
    d_total_elevation_gain = total_elevation_gain_meters / Decimal("150")
    d_average_heartrate = average_heartrate_bpm / user_max_bpm
    d_average_speed = Decimal("6") - abs(user_speed_max - average_speed_kph)
    return _quantize(d_distance_km * d_total_elevation_gain * d_average_heartrate * d_average_speed, "0.0001")
