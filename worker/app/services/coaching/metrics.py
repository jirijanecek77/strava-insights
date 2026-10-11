"""Pure stream calculations that give the coaching prompt a compact view of one activity."""

from numbers import Real

MIN_DECOUPLING_DURATION_SECONDS = 20 * 60


def format_duration(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_pace(seconds_per_km: float | int | None) -> str | None:
    if seconds_per_km is None or seconds_per_km <= 0:
        return None
    return f"{format_duration(seconds_per_km)} /km"


def split_length_meters(sport_type: str, distance_meters: float) -> int:
    if sport_type == "Run":
        return 1000 if distance_meters <= 30000 else 5000
    return 5000 if distance_meters <= 100000 else 10000


def compute_splits(
    *,
    sport_type: str,
    distance_meters: list,
    time_seconds: list,
    heartrate_bpm: list | None = None,
    altitude_meters: list | None = None,
) -> list[dict]:
    """Split an activity into fixed-distance segments with pace or speed, heart rate, and elevation change."""
    points = _aligned_points(distance_meters, time_seconds)
    if len(points) < 2:
        return []
    total_distance = points[-1][1] - points[0][1]
    if total_distance <= 0:
        return []
    split_length = split_length_meters(sport_type, total_distance)

    splits: list[dict] = []
    start = 0
    boundary = points[0][1] + split_length
    for position in range(1, len(points)):
        index, distance, _ = points[position]
        if distance >= boundary:
            splits.append(
                _split_row(sport_type, points, start, position, heartrate_bpm, altitude_meters, len(splits) + 1)
            )
            start = position
            boundary = distance + split_length
    remaining = points[-1][1] - points[start][1]
    if start < len(points) - 1 and remaining >= split_length * 0.3:
        splits.append(
            _split_row(sport_type, points, start, len(points) - 1, heartrate_bpm, altitude_meters, len(splits) + 1)
        )
    return splits


def heart_rate_zone_shares(
    *,
    time_seconds: list,
    heartrate_bpm: list,
    aet_heart_rate_bpm: float | None,
    ant_heart_rate_bpm: float | None,
) -> dict | None:
    """Share of moving time spent below AeT, between AeT and AnT, and above AnT."""
    if aet_heart_rate_bpm is None or ant_heart_rate_bpm is None:
        return None
    totals = {"below_aet": 0.0, "aet_to_ant": 0.0, "above_ant": 0.0}
    for index in range(1, min(len(time_seconds), len(heartrate_bpm))):
        heart_rate = heartrate_bpm[index]
        previous_time, current_time = time_seconds[index - 1], time_seconds[index]
        if not (_is_number(heart_rate) and _is_number(previous_time) and _is_number(current_time)):
            continue
        duration = _number(current_time) - _number(previous_time)
        # Long gaps are pauses, not time spent at the recorded heart rate.
        if duration <= 0 or duration > 60:
            continue
        if heart_rate < aet_heart_rate_bpm:
            totals["below_aet"] += duration
        elif heart_rate <= ant_heart_rate_bpm:
            totals["aet_to_ant"] += duration
        else:
            totals["above_ant"] += duration
    measured = sum(totals.values())
    if measured <= 0:
        return None
    return {
        "aet_heart_rate_bpm": aet_heart_rate_bpm,
        "ant_heart_rate_bpm": ant_heart_rate_bpm,
        **{f"{key}_percent": round(value * 100 / measured, 1) for key, value in totals.items()},
    }


def aerobic_decoupling_percent(
    *, distance_meters: list, time_seconds: list, heartrate_bpm: list
) -> float | None:
    """Drop in speed-per-heartbeat from the first to the second half of the activity; positive means drift."""
    points = [
        (_number(time_value), _number(distance_value), _number(heart_rate))
        for distance_value, time_value, heart_rate in zip(distance_meters, time_seconds, heartrate_bpm)
        if _is_number(distance_value) and _is_number(time_value) and _is_number(heart_rate) and heart_rate > 0
    ]
    if len(points) < 4:
        return None
    start_time, end_time = points[0][0], points[-1][0]
    if end_time - start_time < MIN_DECOUPLING_DURATION_SECONDS:
        return None
    midpoint = start_time + (end_time - start_time) / 2
    first = [point for point in points if point[0] <= midpoint]
    second = [point for point in points if point[0] >= midpoint]
    first_efficiency = _efficiency(first)
    second_efficiency = _efficiency(second)
    if not first_efficiency or second_efficiency is None:
        return None
    return round((first_efficiency - second_efficiency) * 100 / first_efficiency, 1)


def _efficiency(points: list[tuple[float, float, float]]) -> float | None:
    if len(points) < 2:
        return None
    duration = points[-1][0] - points[0][0]
    distance = points[-1][1] - points[0][1]
    average_heart_rate = sum(point[2] for point in points) / len(points)
    if duration <= 0 or distance <= 0 or average_heart_rate <= 0:
        return None
    return (distance / duration) / average_heart_rate


def _split_row(
    sport_type: str,
    points: list[tuple[int, float, float]],
    start: int,
    end: int,
    heartrate_bpm: list | None,
    altitude_meters: list | None,
    number: int,
) -> dict:
    start_index, start_distance, start_time = points[start]
    end_index, end_distance, end_time = points[end]
    distance = end_distance - start_distance
    duration = end_time - start_time
    row: dict = {"split": number, "distance_km": round(distance / 1000, 2)}
    if duration > 0 and distance > 0:
        if sport_type == "Run":
            row["pace"] = format_pace(duration * 1000 / distance)
        else:
            row["speed_kph"] = round(distance / duration * 3.6, 1)
    heart_rates = [
        _number(value)
        for value in (heartrate_bpm or [])[start_index : end_index + 1]
        if _is_number(value) and value > 0
    ]
    if heart_rates:
        row["avg_hr_bpm"] = round(sum(heart_rates) / len(heart_rates))
    altitudes = altitude_meters or []
    if end_index < len(altitudes) and _is_number(altitudes[start_index]) and _is_number(altitudes[end_index]):
        row["elevation_change_m"] = round(_number(altitudes[end_index]) - _number(altitudes[start_index]))
    return row


def _aligned_points(distance_meters: list, time_seconds: list) -> list[tuple[int, float, float]]:
    return [
        (index, _number(distance_value), _number(time_value))
        for index, (distance_value, time_value) in enumerate(zip(distance_meters or [], time_seconds or []))
        if _is_number(distance_value) and _is_number(time_value)
    ]


def _is_number(value) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _number(value) -> float:
    return float(value)
