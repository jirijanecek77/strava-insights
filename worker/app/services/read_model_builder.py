import logging
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.models import ActivityStream, BestEffort, PeriodSummary
from app.repositories import (
    ActivityRepository,
    ActivityStreamRepository,
    BestEffortRepository,
    PeriodSummaryRepository,
)
from app.services.stream_sanitizer import sanitize_persisted_stream

RUN_SPORT = "Run"
RIDE_SPORTS = {"Ride", "EBikeRide"}
RUN_BEST_EFFORT_DISTANCES = {
    "1km": 1000.0,
    "5km": 5000.0,
    "10km": 10000.0,
    "Half-Marathon": 21097.5,
}
RIDE_BEST_EFFORT_DISTANCES = {
    "10km": 10000.0,
    "20km": 20000.0,
    "50km": 50000.0,
    "100km": 100000.0,
}
TOP_EFFORTS_PER_DISTANCE = 5
logger = logging.getLogger(__name__)


def _quantize(value: Decimal, precision: str) -> Decimal:
    return value.quantize(Decimal(precision), rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class AggregateInput:
    sport_type: str
    start_date_local: date
    distance_meters: Decimal
    moving_time_seconds: int
    total_elevation_gain_meters: Decimal | None


class ReadModelBuilder:
    def __init__(self, session) -> None:
        self.session = session
        self.activities = ActivityRepository(session)
        self.activity_streams = ActivityStreamRepository(session)
        self.period_summaries = PeriodSummaryRepository(session)
        self.best_efforts = BestEffortRepository(session)

    def rebuild_for_user(
        self,
        user_id: int,
        *,
        source_run_efforts: dict[int, dict[str, int]] | None = None,
    ) -> None:
        logger.info("Rebuilding read models for user.", extra={"user.id": user_id})
        activities = self.activities.list_for_user(user_id)
        supported_activities = [
            activity
            for activity in activities
            if activity.sport_type == RUN_SPORT or activity.sport_type in RIDE_SPORTS
        ]
        streams = {
            stream.activity_id: stream
            for stream in self.activity_streams.get_by_activity_ids(
                [activity.id for activity in supported_activities]
            )
        }
        sanitized_stream_count = self._sanitize_streams(supported_activities, streams)
        self.period_summaries.replace_for_user(
            user_id=user_id,
            summaries=self._build_period_summaries(user_id, activities),
        )
        best_efforts = self._build_best_efforts(
            user_id,
            supported_activities,
            streams,
            source_run_efforts=source_run_efforts or {},
        )
        self.best_efforts.replace_for_user(user_id=user_id, efforts=best_efforts)
        logger.info(
            "Finished rebuilding read models for user.",
            extra={
                "user.id": user_id,
                "activity_count": len(activities),
                "best_effort_count": len(best_efforts),
                "sanitized_stream_count": sanitized_stream_count,
            },
        )

    def _sanitize_streams(
        self, activities: list, streams: dict[int, ActivityStream]
    ) -> int:
        sanitized_count = 0
        for activity in activities:
            stream = streams.get(activity.id)
            if stream is None or not sanitize_persisted_stream(
                stream, activity.sport_type
            ):
                continue
            self.activity_streams.save(stream)
            sanitized_count += 1
        return sanitized_count

    def _build_period_summaries(
        self, user_id: int, activities: list
    ) -> list[PeriodSummary]:
        aggregate_inputs = [
            AggregateInput(
                sport_type=activity.sport_type,
                start_date_local=(
                    activity.start_date_local or activity.start_date_utc
                ).date(),
                distance_meters=Decimal(str(activity.distance_meters)),
                moving_time_seconds=activity.moving_time_seconds,
                total_elevation_gain_meters=(
                    None
                    if activity.total_elevation_gain_meters is None
                    else Decimal(str(activity.total_elevation_gain_meters))
                ),
            )
            for activity in activities
        ]

        period_summaries: list[PeriodSummary] = []
        for period_type in ("week", "month", "year"):
            period_summaries.extend(
                self._aggregate_period(user_id, aggregate_inputs, period_type)
            )
        return period_summaries

    def _aggregate_period(
        self, user_id: int, activities: list[AggregateInput], period_type: str
    ) -> list[PeriodSummary]:
        grouped: dict[tuple[str, date], list[AggregateInput]] = {}
        for activity in activities:
            if period_type == "week":
                period_start = activity.start_date_local - timedelta(
                    days=activity.start_date_local.weekday()
                )
            else:
                period_start = activity.start_date_local.replace(day=1)
            if period_type == "year":
                period_start = period_start.replace(month=1, day=1)
            grouped.setdefault((activity.sport_type, period_start), []).append(activity)

        summaries: list[PeriodSummary] = []
        for (sport_type, period_start), items in grouped.items():
            total_distance = sum((item.distance_meters for item in items), Decimal("0"))
            total_moving_time = sum(item.moving_time_seconds for item in items)
            total_elevation = sum(
                (item.total_elevation_gain_meters or Decimal("0") for item in items),
                Decimal("0"),
            )
            average_speed_mps = None
            average_pace_seconds_per_km = None
            if total_distance > 0 and total_moving_time > 0:
                if sport_type == RUN_SPORT:
                    average_pace_seconds_per_km = _quantize(
                        (Decimal(total_moving_time) * Decimal("1000")) / total_distance,
                        "0.01",
                    )
                elif sport_type in RIDE_SPORTS:
                    average_speed_mps = _quantize(
                        total_distance / Decimal(total_moving_time), "0.0001"
                    )
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
                )
            )
        return summaries

    def _build_best_efforts(
        self,
        user_id: int,
        activities: list,
        streams: dict[int, ActivityStream],
        *,
        source_run_efforts: dict[int, dict[str, int]],
    ) -> list[BestEffort]:
        candidates_by_code: dict[tuple[str, str], list[BestEffort]] = {}

        for activity in activities:
            source_efforts = source_run_efforts.get(activity.source_activity_id)
            if activity.sport_type == RUN_SPORT and source_efforts is not None:
                for effort_code, best_time in source_efforts.items():
                    target_distance = RUN_BEST_EFFORT_DISTANCES.get(effort_code)
                    if target_distance is not None:
                        self._add_effort_candidate(
                            candidates_by_code,
                            user_id=user_id,
                            activity=activity,
                            effort_code=effort_code,
                            target_distance=target_distance,
                            best_time=best_time,
                        )
                continue

            stream = streams.get(activity.id)
            if (
                stream is None
                or stream.distance_stream is None
                or stream.time_stream is None
            ):
                continue
            distance_values = stream.distance_stream.get("data", [])
            time_values = stream.time_stream.get("data", [])
            effort_distances = (
                RUN_BEST_EFFORT_DISTANCES
                if activity.sport_type == RUN_SPORT
                else RIDE_BEST_EFFORT_DISTANCES
            )
            for effort_code, target_distance in effort_distances.items():
                local_best_time = self._best_time_for_distance(
                    distance_values, time_values, target_distance
                )
                if local_best_time is None:
                    continue
                self._add_effort_candidate(
                    candidates_by_code,
                    user_id=user_id,
                    activity=activity,
                    effort_code=effort_code,
                    target_distance=target_distance,
                    best_time=local_best_time,
                )

        top_efforts: list[BestEffort] = []
        for candidates in candidates_by_code.values():
            candidates.sort(
                key=lambda effort: (
                    effort.best_time_seconds,
                    (
                        effort.achieved_at.isoformat()
                        if effort.achieved_at is not None
                        else ""
                    ),
                    effort.activity_id or 0,
                )
            )
            top_efforts.extend(candidates[:TOP_EFFORTS_PER_DISTANCE])
        return top_efforts

    @staticmethod
    def _add_effort_candidate(
        candidates_by_code: dict[tuple[str, str], list[BestEffort]],
        *,
        user_id: int,
        activity,
        effort_code: str,
        target_distance: float,
        best_time: int,
    ) -> None:
        if best_time <= 0:
            return
        candidate = BestEffort(
            user_id=user_id,
            sport_type=activity.sport_type,
            effort_code=effort_code,
            best_time_seconds=best_time,
            distance_meters=Decimal(str(target_distance)),
            activity_id=activity.id,
            achieved_at=activity.start_date_utc,
        )
        candidates_by_code.setdefault((activity.sport_type, effort_code), []).append(
            candidate
        )

    @staticmethod
    def _best_time_for_distance(
        distance_stream_meters: list[float],
        time_stream_seconds: list[int],
        target_distance: float,
    ) -> int | None:
        samples = [
            (float(distance), float(timestamp))
            for distance, timestamp in zip(distance_stream_meters, time_stream_seconds)
            if isinstance(distance, int | float)
            and not isinstance(distance, bool)
            and isinstance(timestamp, int | float)
            and not isinstance(timestamp, bool)
        ]
        if len(samples) < 2:
            return None

        best_time: int | None = None
        end_index = 1
        for start_index, (start_distance, start_time) in enumerate(samples):
            end_index = max(end_index, start_index + 1)
            target = start_distance + target_distance
            while end_index < len(samples) and samples[end_index][0] < target:
                end_index += 1
            if end_index >= len(samples):
                break
            elapsed = round(samples[end_index][1] - start_time)
            if elapsed <= 0:
                continue
            if best_time is None or elapsed < best_time:
                best_time = elapsed
        return best_time
