from numbers import Real
from typing import Any


def moving_average(data: list[float], range_points: int) -> list[float]:
    if not data or range_points <= 0:
        return []

    data = _numeric_series(data)
    averages: list[float] = []
    length = len(data)
    for index in range(length):
        start = max(0, index - range_points)
        end = min(length, index + range_points + 1)
        window = data[start:end]
        averages.append(sum(window) / len(window))
    return averages


def meters_to_kilometers(distance_stream_meters: list[float]) -> list[float]:
    return [distance / 1000 for distance in _numeric_series(distance_stream_meters)]


def moving_average_speed_kph(
    velocity_smooth_stream_mps: list[float], range_points: int = 10
) -> list[float]:
    return moving_average(
        [speed * 3.6 for speed in _numeric_series(velocity_smooth_stream_mps)],
        range_points=range_points,
    )


def moving_average_heartrate(
    heartrate_stream_bpm: list[float], range_points: int = 10
) -> list[float]:
    return moving_average(heartrate_stream_bpm, range_points=range_points)


def calculate_pace_minutes_per_km(
    seconds: list[int],
    distances_meters: list[float],
    range_points: int = 20,
) -> list[float]:
    numeric_seconds = _numeric_series(seconds)
    numeric_distances = _numeric_series(distances_meters)
    sample_count = min(len(numeric_seconds), len(numeric_distances))
    paces: list[float] = []
    for index in range(sample_count):
        start_index = max(0, index - range_points)
        end_index = min(sample_count - 1, index + range_points)
        total_time_seconds = numeric_seconds[end_index] - numeric_seconds[start_index]
        total_distance_meters = (
            numeric_distances[end_index] - numeric_distances[start_index]
        )

        if total_distance_meters == 0:
            paces.append(16.0)
            continue

        total_time_minutes = total_time_seconds / 60
        total_distance_km = total_distance_meters / 1000
        paces.append(min(16, total_time_minutes / total_distance_km))
    return paces


def format_pace_minutes_per_km(paces: list[float]) -> list[str]:
    import math

    formatted: list[str] = []
    for pace in paces:
        if not math.isfinite(pace):
            formatted.append("0:00")
            continue
        whole_minutes = int(pace)
        seconds = int((pace - whole_minutes) * 60)
        formatted.append(f"{whole_minutes}:{seconds:02d}")
    return formatted


def calculate_slope_percent(
    altitude_stream_meters: list[float],
    distance_stream_meters: list[float],
    range_points: int = 30,
) -> list[float]:
    if not altitude_stream_meters or not distance_stream_meters:
        return []

    altitude_stream_meters = _numeric_series(altitude_stream_meters)
    distance_stream_meters = _numeric_series(distance_stream_meters)
    sample_count = min(len(altitude_stream_meters), len(distance_stream_meters))
    altitude_stream_meters = altitude_stream_meters[:sample_count]
    distance_stream_meters = distance_stream_meters[:sample_count]
    slopes = [0.0] * (range_points // 2)
    for index in range(range_points, len(altitude_stream_meters)):
        elevation_change = (
            altitude_stream_meters[index] - altitude_stream_meters[index - range_points]
        )
        horizontal_distance = (
            distance_stream_meters[index] - distance_stream_meters[index - range_points]
        )
        if horizontal_distance <= 0:
            slopes.append(0.0)
            continue
        slope = (elevation_change / horizontal_distance) * 100
        slopes.append(min(45.0, max(-45.0, slope)))
    return slopes + ([0.0] * (len(distance_stream_meters) - len(slopes)))


def _numeric_series(values: list[Any]) -> list[float]:
    normalized: list[float] = []
    previous = 0.0
    for value in values:
        if isinstance(value, Real) and not isinstance(value, bool):
            previous = float(value)
        normalized.append(previous)
    return normalized
