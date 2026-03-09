from dataclasses import dataclass


BEST_EFFORT_DISTANCES = {
    "1km": 1000.0,
    "5km": 5000.0,
    "10km": 10000.0,
    "Half-Marathon": 21097.5,
}


@dataclass(slots=True)
class BestEffortResult:
    effort_code: str
    distance_meters: float
    best_time_seconds: int
    activity_id: int
    achieved_at: object


def derive_activity_best_efforts(
    *,
    activity_id: int,
    achieved_at,
    distance_stream_meters: list[float],
    time_stream_seconds: list[int],
) -> list[BestEffortResult]:
    if not distance_stream_meters or not time_stream_seconds or len(distance_stream_meters) != len(time_stream_seconds):
        return []

    results: list[BestEffortResult] = []
    for effort_code, target_distance in BEST_EFFORT_DISTANCES.items():
        best_time = _best_time_for_distance(distance_stream_meters, time_stream_seconds, target_distance)
        if best_time is None:
            continue
        results.append(
            BestEffortResult(
                effort_code=effort_code,
                distance_meters=target_distance,
                best_time_seconds=best_time,
                activity_id=activity_id,
                achieved_at=achieved_at,
            )
        )
    return results


def _best_time_for_distance(distance_stream_meters: list[float], time_stream_seconds: list[int], target_distance: float) -> int | None:
    best_time: int | None = None
    for start_index in range(len(distance_stream_meters)):
        start_distance = distance_stream_meters[start_index]
        end_index = _first_index_at_distance(distance_stream_meters, start_index, start_distance + target_distance)
        if end_index is None:
            continue
        elapsed = time_stream_seconds[end_index] - time_stream_seconds[start_index]
        if best_time is None or elapsed < best_time:
            best_time = elapsed
    return best_time


def _first_index_at_distance(distance_stream_meters: list[float], start_index: int, target_distance: float) -> int | None:
    for index in range(start_index, len(distance_stream_meters)):
        if distance_stream_meters[index] >= target_distance:
            return index
    return None
