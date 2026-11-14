"""Normalize chronological Garmin lap DTOs; no provider objects leave the adapter."""

from math import isfinite


def _number(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        return None
    return float(value) if (value > 0 if positive else value >= 0) else None


def normalize_recorded_splits(payload: dict) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get("lapDTOs"), list):
        raise ValueError("Unexpected Garmin splits response.")
    rows = payload["lapDTOs"]
    # lapIndex is the recorded order; never use grouped split summaries as laps.
    rows = sorted(enumerate(rows), key=lambda item: _number(item[1].get("lapIndex"))
                  if isinstance(item[1], dict) and _number(item[1].get("lapIndex")) is not None else item[0] + 1)
    laps = []
    distance = 0.0
    timer = 0.0
    for _, row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid Garmin lap.")
        length = _number(row.get("distance"))
        if length is None:
            # Unknown length makes all later cumulative distances ambiguous; retry instead of shifting laps.
            raise ValueError("Garmin lap has no valid distance.")
        duration = _number(row.get("duration"))
        moving = _number(row.get("movingDuration"))
        elapsed = _number(row.get("elapsedDuration"))
        speed = _number(row.get("averageSpeed"), positive=True)
        # averageSpeed uses Garmin timer duration, excluding timer stops but retaining timed recoveries.
        # averageMovingSpeed can remove low-speed recovery, so it is deliberately not substituted here.
        if speed is None and duration and length:
            speed = length / duration
        lap_type = row.get("intensityType")
        laps.append({
            "number": len(laps) + 1,
            "lap_type": lap_type[:40] if isinstance(lap_type, str) else None,
            "start_distance_meters": round(distance, 3),
            "end_distance_meters": round(distance + length, 3),
            "distance_meters": length,
            "start_timer_seconds": timer,
            "duration_seconds": duration,
            "moving_duration_seconds": moving,
            "elapsed_duration_seconds": elapsed,
            "average_speed_kph": round(speed * 3.6, 4) if speed else None,
            "average_pace_seconds_per_km": round(1000 / speed, 4) if speed else None,
            "average_heartrate_bpm": _number(row.get("averageHR"), positive=True),
            "elevation_gain_meters": _number(row.get("elevationGain")),
            "elevation_loss_meters": _number(row.get("elevationLoss")),
        })
        distance += length
        timer = timer + duration if timer is not None and duration is not None else None
    return laps
