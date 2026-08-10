from math import asin, cos, isfinite, radians, sin, sqrt
from numbers import Real
from typing import Any

RUN_MAX_SPEED_MPS = 12.0
RIDE_MAX_SPEED_MPS = 50.0
MIN_HEART_RATE_BPM = 30.0
MAX_HEART_RATE_BPM = 240.0
MAX_HEART_RATE_CHANGE_BPM_PER_SECOND = 20.0


def sanitize_stream_payload(payload: dict[str, Any], sport_type: str) -> dict[str, Any]:
    time_values = _stream_data(payload.get("time"))
    max_speed = RUN_MAX_SPEED_MPS if sport_type == "Run" else RIDE_MAX_SPEED_MPS
    sanitized = dict(payload)
    sanitized["time"] = _with_data(payload.get("time"), _sanitize_time(time_values))
    sanitized_time = _stream_data(sanitized["time"])
    sanitized["distance"] = _with_data(
        payload.get("distance"),
        _sanitize_distance(
            _stream_data(payload.get("distance")), sanitized_time, max_speed
        ),
    )
    sanitized["latlng"] = _with_data(
        payload.get("latlng"),
        _sanitize_latlng(
            _stream_data(payload.get("latlng")), sanitized_time, max_speed
        ),
    )
    sanitized["altitude"] = _with_data(
        payload.get("altitude"),
        _sanitize_altitude(
            _stream_data(payload.get("altitude")), sanitized_time, sport_type
        ),
    )
    sanitized["velocity_smooth"] = _with_data(
        payload.get("velocity_smooth"),
        _sanitize_speed(_stream_data(payload.get("velocity_smooth")), max_speed),
    )
    sanitized["heartrate"] = _with_data(
        payload.get("heartrate"),
        _sanitize_heartrate(_stream_data(payload.get("heartrate")), sanitized_time),
    )
    return sanitized


def sanitize_persisted_stream(stream: Any, sport_type: str) -> bool:
    payload = {
        "time": stream.time_stream,
        "distance": stream.distance_stream,
        "latlng": stream.latlng_stream,
        "altitude": stream.altitude_stream,
        "velocity_smooth": stream.velocity_smooth_stream,
        "heartrate": stream.heartrate_stream,
    }
    sanitized = sanitize_stream_payload(payload, sport_type)
    changed = any(sanitized[key] != payload[key] for key in payload)
    if not changed:
        return False
    stream.time_stream = sanitized["time"]
    stream.distance_stream = sanitized["distance"]
    stream.latlng_stream = sanitized["latlng"]
    stream.altitude_stream = sanitized["altitude"]
    stream.velocity_smooth_stream = sanitized["velocity_smooth"]
    stream.heartrate_stream = sanitized["heartrate"]
    return True


def _sanitize_time(values: list[Any]) -> list[float | None]:
    sanitized: list[float | None] = []
    previous: float | None = None
    for value in values:
        numeric = _finite_number(value)
        if (
            numeric is None
            or numeric < 0
            or (previous is not None and numeric < previous)
        ):
            sanitized.append(None)
            continue
        sanitized.append(numeric)
        previous = numeric
    return sanitized


def _sanitize_distance(
    values: list[Any], times: list[Any], max_speed_mps: float
) -> list[float | None]:
    sanitized: list[float | None] = []
    previous_distance: float | None = None
    previous_time: float | None = None
    correction = 0.0
    for index, value in enumerate(values):
        raw_distance = _finite_number(value)
        timestamp = _finite_number(times[index]) if index < len(times) else None
        if raw_distance is None or raw_distance < 0 or timestamp is None:
            sanitized.append(None)
            continue

        corrected_distance = max(0.0, raw_distance - correction)
        if previous_distance is not None and previous_time is not None:
            elapsed = timestamp - previous_time
            if elapsed <= 0:
                sanitized.append(
                    previous_distance
                    if corrected_distance == previous_distance
                    else None
                )
                continue
            if corrected_distance < previous_distance:
                corrected_distance = previous_distance
            maximum_distance = previous_distance + (max_speed_mps * elapsed)
            if corrected_distance > maximum_distance:
                correction += corrected_distance - maximum_distance
                corrected_distance = maximum_distance

        sanitized.append(corrected_distance)
        previous_distance = corrected_distance
        previous_time = timestamp
    return sanitized


def _sanitize_speed(values: list[Any], max_speed_mps: float) -> list[float | None]:
    return [
        numeric if numeric is not None and 0 <= numeric <= max_speed_mps else None
        for numeric in (_finite_number(value) for value in values)
    ]


def _sanitize_heartrate(values: list[Any], times: list[Any]) -> list[float | None]:
    sanitized: list[float | None] = []
    previous_value: float | None = None
    previous_time: float | None = None
    for index, value in enumerate(values):
        numeric = _finite_number(value)
        timestamp = _finite_number(times[index]) if index < len(times) else None
        if (
            numeric is None
            or timestamp is None
            or not MIN_HEART_RATE_BPM <= numeric <= MAX_HEART_RATE_BPM
        ):
            sanitized.append(None)
            continue
        if previous_value is not None and previous_time is not None:
            elapsed = timestamp - previous_time
            if (
                elapsed <= 0
                or abs(numeric - previous_value) / elapsed
                > MAX_HEART_RATE_CHANGE_BPM_PER_SECOND
            ):
                sanitized.append(None)
                continue
        sanitized.append(numeric)
        previous_value = numeric
        previous_time = timestamp
    return sanitized


def _sanitize_altitude(
    values: list[Any], times: list[Any], sport_type: str
) -> list[float | None]:
    max_vertical_speed = 8.0 if sport_type == "Run" else 15.0
    sanitized: list[float | None] = []
    previous_value: float | None = None
    previous_time: float | None = None
    for index, value in enumerate(values):
        numeric = _finite_number(value)
        timestamp = _finite_number(times[index]) if index < len(times) else None
        if numeric is None or timestamp is None or not -500 <= numeric <= 9000:
            sanitized.append(None)
            continue
        if previous_value is not None and previous_time is not None:
            elapsed = timestamp - previous_time
            if (
                elapsed <= 0
                or abs(numeric - previous_value) / elapsed > max_vertical_speed
            ):
                sanitized.append(None)
                continue
        sanitized.append(numeric)
        previous_value = numeric
        previous_time = timestamp
    return sanitized


def _sanitize_latlng(
    values: list[Any], times: list[Any], max_speed_mps: float
) -> list[list[float] | None]:
    sanitized: list[list[float] | None] = []
    previous_point: list[float] | None = None
    previous_time: float | None = None
    for index, value in enumerate(values):
        point = _coordinate(value)
        timestamp = _finite_number(times[index]) if index < len(times) else None
        if point is None or timestamp is None:
            sanitized.append(None)
            continue
        if previous_point is not None and previous_time is not None:
            elapsed = timestamp - previous_time
            if (
                elapsed <= 0
                or _haversine_meters(previous_point, point) / elapsed > max_speed_mps
            ):
                sanitized.append(None)
                continue
        sanitized.append(point)
        previous_point = point
        previous_time = timestamp
    return sanitized


def _coordinate(value: Any) -> list[float] | None:
    if not isinstance(value, list | tuple) or len(value) < 2:
        return None
    latitude = _finite_number(value[0])
    longitude = _finite_number(value[1])
    if (
        latitude is None
        or longitude is None
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        return None
    return [latitude, longitude]


def _haversine_meters(left: list[float], right: list[float]) -> float:
    left_lat, left_lng = radians(left[0]), radians(left[1])
    right_lat, right_lng = radians(right[0]), radians(right[1])
    delta_lat = right_lat - left_lat
    delta_lng = right_lng - left_lng
    value = (
        sin(delta_lat / 2) ** 2
        + cos(left_lat) * cos(right_lat) * sin(delta_lng / 2) ** 2
    )
    return 6_371_000 * 2 * asin(sqrt(value))


def _stream_data(stream: Any) -> list[Any]:
    if not isinstance(stream, dict) or not isinstance(stream.get("data"), list):
        return []
    return stream["data"]


def _with_data(stream: Any, data: list[Any]) -> dict[str, Any] | None:
    if stream is None and not data:
        return None
    base = dict(stream) if isinstance(stream, dict) else {}
    base["data"] = data
    return base


def _finite_number(value: Any) -> float | None:
    if not isinstance(value, Real) or isinstance(value, bool):
        return None
    numeric = float(value)
    return numeric if isfinite(numeric) else None
