from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.models import ActivityBestEffort, BestEffort, PeriodSummary
from app.repositories import (
    ActivityBestEffortRepository,
    ActivityRepository,
    ActivityStreamRepository,
    BestEffortRepository,
    PeriodSummaryRepository,
)


RUN_SPORT = "Run"
RIDE_SPORTS = {"Ride", "EBikeRide"}
BEST_EFFORT_DISTANCES = {
    "1km": 1000.0,
    "5km": 5000.0,
    "10km": 10000.0,
    "Half-Marathon": 21097.5,
}


def _quantize(value: Decimal, precision: str) -> Decimal:
    return value.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class AggregateInput:
    sport_type: str
    start_date_local: date
    distance_meters: Decimal
    moving_time_seconds: int
    total_elevation_gain_meters: Decimal | None
    difficulty_score: Decimal | None


class ReadModelBuilder:
    def __init__(self, session) -> None:
        self.session = session
        self.activities = ActivityRepository(session)
        self.activity_streams = ActivityStreamRepository(session)
        self.period_summaries = PeriodSummaryRepository(session)
        self.best_efforts = BestEffortRepository(session)
        self.activity_best_efforts = ActivityBestEffortRepository(session)

    def rebuild_for_user(self, user_id: int) -> None:
        activities = self.activities.list_for_user(user_id)
        self.period_summaries.replace_for_user(
            user_id=user_id,
            summaries=self._build_period_summaries(user_id, activities),
        )
        best_efforts, activity_best_efforts = self._build_best_efforts(user_id, activities)
        self.best_efforts.replace_for_user(user_id=user_id, efforts=best_efforts)
        self.activity_best_efforts.replace_for_activities(
            activity_ids=[activity.id for activity in activities],
            efforts=activity_best_efforts,
        )

    def _build_period_summaries(self, user_id: int, activities: list) -> list[PeriodSummary]:
        aggregate_inputs = [
            AggregateInput(
                sport_type=activity.sport_type,
                start_date_local=(activity.start_date_local or activity.start_date_utc).date(),
                distance_meters=Decimal(str(activity.distance_meters)),
                moving_time_seconds=activity.moving_time_seconds,
                total_elevation_gain_meters=None
                if activity.total_elevation_gain_meters is None
                else Decimal(str(activity.total_elevation_gain_meters)),
                difficulty_score=None if activity.difficulty_score is None else Decimal(str(activity.difficulty_score)),
            )
            for activity in activities
        ]

        period_summaries: list[PeriodSummary] = []
        for period_type in ("month", "year"):
            period_summaries.extend(self._aggregate_period(user_id, aggregate_inputs, period_type))
        return period_summaries

    def _aggregate_period(self, user_id: int, activities: list[AggregateInput], period_type: str) -> list[PeriodSummary]:
        grouped: dict[tuple[str, date], list[AggregateInput]] = {}
        for activity in activities:
            period_start = activity.start_date_local.replace(day=1)
            if period_type == "year":
                period_start = period_start.replace(month=1, day=1)
            grouped.setdefault((activity.sport_type, period_start), []).append(activity)

        summaries: list[PeriodSummary] = []
        for (sport_type, period_start), items in grouped.items():
            total_distance = sum((item.distance_meters for item in items), Decimal("0"))
            total_moving_time = sum(item.moving_time_seconds for item in items)
            total_elevation = sum((item.total_elevation_gain_meters or Decimal("0") for item in items), Decimal("0"))
            total_difficulty = sum((item.difficulty_score or Decimal("0") for item in items), Decimal("0"))
            average_speed_mps = None
            average_pace_seconds_per_km = None
            if total_distance > 0 and total_moving_time > 0:
                if sport_type == RUN_SPORT:
                    average_pace_seconds_per_km = _quantize(
                        (Decimal(total_moving_time) * Decimal("1000")) / total_distance,
                        "0.01",
                    )
                elif sport_type in RIDE_SPORTS:
                    average_speed_mps = _quantize(total_distance / Decimal(total_moving_time), "0.0001")

            summaries.append(
                PeriodSummary(
                    user_id=user_id,
                    sport_type=sport_type,
                    period_type=period_type,
                    period_start=period_start,
                    activity_count=len(items),
                    total_distance_meters=_quantize(total_distance, "0.01"),
                    total_moving_time_seconds=total_moving_time,
                    average_speed_mps=average_speed_mps,
                    average_pace_seconds_per_km=average_pace_seconds_per_km,
                    total_elevation_gain_meters=_quantize(total_elevation, "0.01"),
                    total_difficulty_score=_quantize(total_difficulty, "0.0001"),
                )
            )
        return summaries

    def _build_best_efforts(self, user_id: int, activities: list) -> tuple[list[BestEffort], list[ActivityBestEffort]]:
        run_activities = [activity for activity in activities if activity.sport_type == RUN_SPORT]
        streams = {stream.activity_id: stream for stream in self.activity_streams.get_by_activity_ids([activity.id for activity in run_activities])}
        all_activity_efforts: list[ActivityBestEffort] = []
        best_by_code: dict[str, BestEffort] = {}

        for activity in run_activities:
            stream = streams.get(activity.id)
            if stream is None or stream.distance_stream is None or stream.time_stream is None:
                continue
            distance_values = stream.distance_stream.get("data", [])
            time_values = stream.time_stream.get("data", [])
            for effort_code, target_distance in BEST_EFFORT_DISTANCES.items():
                best_time = self._best_time_for_distance(distance_values, time_values, target_distance)
                if best_time is None:
                    continue
                all_activity_efforts.append(
                    ActivityBestEffort(activity_id=activity.id, effort_code=effort_code, best_time_seconds=best_time)
                )
                current_best = best_by_code.get(effort_code)
                if current_best is None or best_time < current_best.best_time_seconds:
                    best_by_code[effort_code] = BestEffort(
                        user_id=user_id,
                        sport_type=RUN_SPORT,
                        effort_code=effort_code,
                        best_time_seconds=best_time,
                        distance_meters=Decimal(str(target_distance)),
                        activity_id=activity.id,
                        achieved_at=activity.start_date_utc,
                    )

        return list(best_by_code.values()), all_activity_efforts

    @staticmethod
    def _best_time_for_distance(distance_stream_meters: list[float], time_stream_seconds: list[int], target_distance: float) -> int | None:
        best_time: int | None = None
        for start_index, start_distance in enumerate(distance_stream_meters):
            end_index = None
            for index in range(start_index, len(distance_stream_meters)):
                if distance_stream_meters[index] >= start_distance + target_distance:
                    end_index = index
                    break
            if end_index is None:
                continue
            elapsed = time_stream_seconds[end_index] - time_stream_seconds[start_index]
            if best_time is None or elapsed < best_time:
                best_time = elapsed
        return best_time
