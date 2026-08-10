from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RankedEffort:
    effort: Any
    rank: int
    pace_seconds_per_km: float | None
    average_speed_kph: float | None


def rank_best_efforts(efforts: list[Any]) -> list[RankedEffort]:
    ranks: dict[tuple[str, str], int] = {}
    ranked: list[RankedEffort] = []
    for effort in efforts:
        key = (effort.sport_type, effort.effort_code)
        rank = ranks.get(key, 0) + 1
        ranks[key] = rank
        distance_meters = float(effort.distance_meters)
        best_time_seconds = float(effort.best_time_seconds)
        pace_seconds_per_km = None
        average_speed_kph = None
        if distance_meters > 0 and best_time_seconds > 0:
            if effort.sport_type == "Run":
                pace_seconds_per_km = round(
                    best_time_seconds * 1000 / distance_meters, 2
                )
            else:
                average_speed_kph = round(
                    (distance_meters / best_time_seconds) * 3.6, 2
                )
        ranked.append(
            RankedEffort(
                effort=effort,
                rank=rank,
                pace_seconds_per_km=pace_seconds_per_km,
                average_speed_kph=average_speed_kph,
            )
        )
    return ranked
