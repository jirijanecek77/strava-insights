from datetime import date
from math import isfinite
from numbers import Real
from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.analytics.service import ActivityDetailAnalyticsService
from app.application.read_models.effort_rankings import rank_best_efforts
from app.domain.schemas.activity import (
    ActivityDetailResponse,
    ActivityDetailThresholds,
    ActivityEffortRank,
    ActivityKpis,
    ActivityListResponse,
    ActivityListRow,
    ActivityMap,
    ActivitySeries,
    RouteComparisonAttempt,
    RouteComparisonResponse,
)
from app.infrastructure.repositories.activity_repository import ActivityRepository
from app.infrastructure.repositories.activity_stream_repository import (
    ActivityStreamRepository,
)
from app.infrastructure.repositories.best_effort_repository import BestEffortRepository
from app.infrastructure.repositories.user_profile_repository import (
    UserProfileRepository,
)


class ActivityReadService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.activities = ActivityRepository(db_session)
        self.streams = ActivityStreamRepository(db_session)
        self.best_efforts = BestEffortRepository(db_session)
        self.user_profiles = UserProfileRepository(db_session)
        self.analytics = ActivityDetailAnalyticsService()

    def list_activities(
        self,
        user_id: int,
        *,
        sport_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> ActivityListResponse:
        items = self.activities.list_for_user(
            user_id,
            sport_type=sport_type,
            date_from=date_from,
            date_to=date_to,
        )
        return ActivityListResponse(
            items=[
                ActivityListRow(
                    id=item.id,
                    sport_type=item.sport_type,
                    name=item.name,
                    start_date_local=item.start_date_local,
                    distance_km=item.distance_km,
                    moving_time_display=item.moving_time_display,
                    summary_metric_display=_format_summary_metric_value(item),
                    summary_metric_kind=_summary_metric_kind(item),
                    total_elevation_gain_meters=item.total_elevation_gain_meters,
                    average_heartrate_bpm=item.average_heartrate_bpm,
                )
                for item in items
            ]
        )

    def get_activity_detail(
        self, user_id: int, activity_id: int
    ) -> ActivityDetailResponse | None:
        activity = self.activities.get_by_id_for_user(activity_id, user_id)
        if activity is None:
            return None

        stream = self.streams.get_for_activity(activity.id)
        activity_local_date = (
            None
            if activity.start_date_local is None
            else activity.start_date_local.date()
        )
        profile = self.user_profiles.get_effective_for_user(
            user_id, activity_local_date
        )
        analytics = self.analytics.build(
            sport_type=activity.sport_type,
            start_date_utc=activity.start_date_utc,
            time_stream=(
                (stream.time_stream or {}).get("data", [])
                if stream and stream.time_stream
                else []
            ),
            distance_stream_meters=(
                (stream.distance_stream or {}).get("data", [])
                if stream and stream.distance_stream
                else []
            ),
            heartrate_stream_bpm=(
                (stream.heartrate_stream or {}).get("data", [])
                if stream and stream.heartrate_stream
                else []
            ),
            altitude_stream_meters=(
                (stream.altitude_stream or {}).get("data", [])
                if stream and stream.altitude_stream
                else []
            ),
            velocity_smooth_stream_mps=(
                (stream.velocity_smooth_stream or {}).get("data", [])
                if stream and stream.velocity_smooth_stream
                else []
            ),
            average_cadence=(
                float(activity.average_cadence)
                if activity.average_cadence is not None
                else None
            ),
            aet_heart_rate_bpm=None if profile is None else profile.aet_heart_rate_bpm,
            ant_heart_rate_bpm=None if profile is None else profile.ant_heart_rate_bpm,
            aet_pace_min_per_km=(
                float(profile.aet_pace_min_per_km)
                if profile is not None and profile.aet_pace_min_per_km is not None
                else None
            ),
            ant_pace_min_per_km=(
                float(profile.ant_pace_min_per_km)
                if profile is not None and profile.ant_pace_min_per_km is not None
                else None
            ),
        )

        latlng = (
            (stream.latlng_stream or {}).get("data", [])
            if stream and stream.latlng_stream
            else []
        )
        activity_map = _activity_map_from_latlng(latlng)
        thresholds = (
            ActivityDetailThresholds(
                aet_heart_rate_bpm=(
                    float(profile.aet_heart_rate_bpm)
                    if profile.aet_heart_rate_bpm is not None
                    else None
                ),
                ant_heart_rate_bpm=(
                    float(profile.ant_heart_rate_bpm)
                    if profile.ant_heart_rate_bpm is not None
                    else None
                ),
                aet_pace_min_per_km=(
                    float(profile.aet_pace_min_per_km)
                    if profile.aet_pace_min_per_km is not None
                    and activity.sport_type == "Run"
                    else None
                ),
                ant_pace_min_per_km=(
                    float(profile.ant_pace_min_per_km)
                    if profile.ant_pace_min_per_km is not None
                    and activity.sport_type == "Run"
                    else None
                ),
            )
            if (
                profile is not None
                and (
                    (
                        activity.sport_type == "Run"
                        and profile.aet_heart_rate_bpm is not None
                        and profile.ant_heart_rate_bpm is not None
                        and profile.aet_pace_min_per_km is not None
                        and profile.ant_pace_min_per_km is not None
                    )
                    or (
                        activity.sport_type in {"Ride", "EBikeRide"}
                        and profile.aet_heart_rate_bpm is not None
                        and profile.ant_heart_rate_bpm is not None
                    )
                )
            )
            else None
        )
        ranked_efforts = rank_best_efforts(self.best_efforts.list_for_user(user_id))
        activity_efforts = [
            ActivityEffortRank(
                rank=item.rank,
                effort_code=item.effort.effort_code,
                best_time_seconds=item.effort.best_time_seconds,
                distance_meters=item.effort.distance_meters,
                pace_seconds_per_km=item.pace_seconds_per_km,
                average_speed_kph=item.average_speed_kph,
            )
            for item in ranked_efforts
            if item.effort.activity_id == activity.id
        ]
        route_comparison = self._build_route_comparison(user_id, activity)
        return ActivityDetailResponse(
            id=activity.id,
            sport_type=activity.sport_type,
            name=activity.name,
            description=activity.description,
            start_date_local=activity.start_date_local,
            kpis=ActivityKpis(
                distance_km=activity.distance_km,
                moving_time_display=activity.moving_time_display,
                elapsed_time_display=_format_elapsed_time(
                    activity.elapsed_time_seconds, activity.moving_time_seconds
                ),
                summary_metric_display=_format_summary_metric_value(activity),
                aerobic_efficiency_m_per_beat=_compute_aerobic_efficiency(
                    activity.average_speed_mps, activity.average_heartrate_bpm
                ),
                summary_metric_kind=_summary_metric_kind(activity),
                total_elevation_gain_meters=activity.total_elevation_gain_meters,
                average_heartrate_bpm=activity.average_heartrate_bpm,
                average_cadence=activity.average_cadence,
                max_pace_display=(
                    _format_max_pace_display(activity.max_speed_mps)
                    if activity.sport_type == "Run"
                    else None
                ),
                max_speed_kph=(
                    _compute_max_speed_kph(activity.max_speed_mps)
                    if activity.sport_type not in {"Run"}
                    else None
                ),
            ),
            map=activity_map,
            series=ActivitySeries(
                distance_km=analytics["distance_km"],
                altitude_meters=analytics["altitude_meters"],
                moving_average_heartrate=analytics["moving_average_heartrate"],
                moving_average_speed_kph=analytics["moving_average_speed_kph"],
                pace_minutes_per_km=analytics["pace_minutes_per_km"],
                pace_display=analytics["pace_display"],
                slope_percent=analytics["slope_percent"],
            ),
            thresholds=thresholds,
            running_analysis=analytics["running_analysis"],
            cycling_analysis=analytics["cycling_analysis"],
            best_efforts=activity_efforts,
            route_comparison=route_comparison,
        )

    def _build_route_comparison(
        self, user_id: int, activity
    ) -> RouteComparisonResponse | None:
        if not activity.intervals_route_id:
            return None
        activities = self.activities.list_for_route(
            user_id,
            route_id=activity.intervals_route_id,
            sport_type=activity.sport_type,
        )
        if len(activities) < 2:
            return None

        attempts: list[RouteComparisonAttempt] = []
        current_rank = 0
        for rank, attempt in enumerate(activities, start=1):
            if attempt.id == activity.id:
                current_rank = rank
            pace_seconds_per_km = None
            average_speed_kph = None
            distance_meters = float(attempt.distance_meters)
            if distance_meters > 0 and attempt.moving_time_seconds > 0:
                if attempt.sport_type == "Run":
                    pace_seconds_per_km = round(
                        attempt.moving_time_seconds * 1000 / distance_meters, 2
                    )
                else:
                    average_speed_kph = round(
                        (distance_meters / attempt.moving_time_seconds) * 3.6,
                        2,
                    )
            attempts.append(
                RouteComparisonAttempt(
                    activity_id=attempt.id,
                    start_date_local=attempt.start_date_local,
                    moving_time_seconds=attempt.moving_time_seconds,
                    distance_km=attempt.distance_km,
                    pace_seconds_per_km=pace_seconds_per_km,
                    average_speed_kph=average_speed_kph,
                    average_heartrate_bpm=attempt.average_heartrate_bpm,
                    rank=rank,
                    is_current=attempt.id == activity.id,
                )
            )
        if current_rank == 0:
            return None

        best_time = activities[0].moving_time_seconds
        route_name = activity.intervals_route_name or next(
            (
                item.intervals_route_name
                for item in activities
                if item.intervals_route_name
            ),
            "Intervals Route",
        )
        return RouteComparisonResponse(
            route_id=activity.intervals_route_id,
            route_name=route_name,
            current_rank=current_rank,
            attempt_count=len(activities),
            best_time_seconds=best_time,
            current_time_seconds=activity.moving_time_seconds,
            difference_seconds=activity.moving_time_seconds - best_time,
            attempts=attempts,
        )


def _activity_map_from_latlng(raw_polyline: Any) -> ActivityMap | None:
    polyline, point_indices, segment_starts = _normalize_route(raw_polyline)
    if not polyline:
        return None
    return ActivityMap(
        polyline=polyline,
        point_indices=point_indices,
        segment_starts=segment_starts,
        bounds=_map_bounds(polyline),
    )


def _normalize_route(
    raw_polyline: Any,
) -> tuple[list[list[float]], list[int], list[int]]:
    if not isinstance(raw_polyline, list):
        return [], [], []

    polyline: list[list[float]] = []
    point_indices: list[int] = []
    segment_starts: list[int] = []
    segment_open = False
    for index, point in enumerate(raw_polyline):
        if not isinstance(point, list | tuple) or len(point) < 2:
            segment_open = False
            continue
        latitude, longitude = point[0], point[1]
        if not _is_coordinate(latitude, minimum=-90, maximum=90) or not _is_coordinate(
            longitude,
            minimum=-180,
            maximum=180,
        ):
            segment_open = False
            continue
        if not segment_open:
            segment_starts.append(len(polyline))
            segment_open = True
        normalized = [float(latitude), float(longitude)]
        polyline.append(normalized)
        point_indices.append(index)
    return polyline, point_indices, segment_starts


def _is_coordinate(value: Any, *, minimum: float, maximum: float) -> bool:
    return (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and isfinite(float(value))
        and minimum <= float(value) <= maximum
    )


def _map_bounds(polyline: list[list[float]]) -> dict[str, float]:
    latitudes = [point[0] for point in polyline]
    longitudes = [point[1] for point in polyline]
    return {
        "min_lat": min(latitudes),
        "max_lat": max(latitudes),
        "min_lng": min(longitudes),
        "max_lng": max(longitudes),
    }


def _format_max_pace_display(max_speed_mps) -> str | None:
    if max_speed_mps is None or float(max_speed_mps) == 0:
        return None
    pace_min_per_km = 1000 / (float(max_speed_mps) * 60)
    whole = int(pace_min_per_km)
    seconds = int((pace_min_per_km - whole) * 60)
    return f"{whole}:{seconds:02d}"


def _compute_max_speed_kph(max_speed_mps) -> float | None:
    if max_speed_mps is None:
        return None
    return round(float(max_speed_mps) * 3.6, 2)


def _compute_aerobic_efficiency(speed_mps, heartrate_bpm) -> float | None:
    if speed_mps is None or heartrate_bpm is None or float(heartrate_bpm) == 0:
        return None
    return round((float(speed_mps) * 3.6 * 1000) / (float(heartrate_bpm) * 60), 2)


def _format_elapsed_time(
    elapsed_seconds: int | None, moving_seconds: int | None
) -> str | None:
    if elapsed_seconds is None or moving_seconds is None:
        return None
    if elapsed_seconds - moving_seconds <= 30:
        return None
    hours, remainder = divmod(elapsed_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _summary_metric_kind(activity) -> str | None:
    if activity.average_pace_display:
        return "pace"
    if activity.average_speed_kph is not None:
        return "speed"
    return None


def _format_summary_metric_value(activity) -> str | None:
    metric_kind = _summary_metric_kind(activity)
    if metric_kind == "pace":
        return activity.average_pace_display
    if metric_kind == "speed" and activity.average_speed_kph is not None:
        return f"{activity.average_speed_kph:.2f}".rstrip("0").rstrip(".")
    return activity.summary_metric_display
