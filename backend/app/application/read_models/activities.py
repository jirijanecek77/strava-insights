from datetime import date

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.analytics.service import ActivityDetailAnalyticsService
from app.domain.schemas.activity import (
    ActivityDetailResponse,
    ActivityKpis,
    ActivityListResponse,
    ActivityListRow,
    ActivityMap,
    ActivitySeries,
)
from app.infrastructure.repositories.activity_repository import ActivityRepository
from app.infrastructure.repositories.activity_stream_repository import ActivityStreamRepository
from app.infrastructure.repositories.user_profile_repository import UserProfileRepository


class ActivityReadService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.activities = ActivityRepository(db_session)
        self.streams = ActivityStreamRepository(db_session)
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
                    summary_metric_display=item.summary_metric_display,
                    total_elevation_gain_meters=item.total_elevation_gain_meters,
                    average_heartrate_bpm=item.average_heartrate_bpm,
                    difficulty_score=item.difficulty_score,
                )
                for item in items
            ]
        )

    def get_activity_detail(self, user_id: int, activity_id: int) -> ActivityDetailResponse | None:
        activity = self.activities.get_by_id_for_user(activity_id, user_id)
        if activity is None:
            return None

        stream = self.streams.get_for_activity(activity.id)
        profile = self.user_profiles.get_for_user(user_id)
        analytics = self.analytics.build(
            sport_type=activity.sport_type,
            start_date_utc=activity.start_date_utc,
            time_stream=(stream.time_stream or {}).get("data", []) if stream and stream.time_stream else [],
            distance_stream_meters=(stream.distance_stream or {}).get("data", []) if stream and stream.distance_stream else [],
            heartrate_stream_bpm=(stream.heartrate_stream or {}).get("data", []) if stream and stream.heartrate_stream else [],
            altitude_stream_meters=(stream.altitude_stream or {}).get("data", []) if stream and stream.altitude_stream else [],
            velocity_smooth_stream_mps=(stream.velocity_smooth_stream or {}).get("data", []) if stream and stream.velocity_smooth_stream else [],
            birthday=None if profile is None else profile.birthday,
            speed_max=None if profile is None else profile.speed_max,
        )

        latlng = (stream.latlng_stream or {}).get("data", []) if stream and stream.latlng_stream else []
        return ActivityDetailResponse(
            id=activity.id,
            sport_type=activity.sport_type,
            name=activity.name,
            description=activity.description,
            start_date_local=activity.start_date_local,
            kpis=ActivityKpis(
                distance_km=activity.distance_km,
                moving_time_display=activity.moving_time_display,
                summary_metric_display=activity.summary_metric_display,
                total_elevation_gain_meters=activity.total_elevation_gain_meters,
                average_heartrate_bpm=activity.average_heartrate_bpm,
                difficulty_score=activity.difficulty_score,
            ),
            map=None if not latlng else ActivityMap(polyline=latlng, bounds=_map_bounds(latlng)),
            series=ActivitySeries(
                distance_km=analytics["distance_km"],
                moving_average_heartrate=analytics["moving_average_heartrate"],
                moving_average_speed_kph=analytics["moving_average_speed_kph"],
                pace_minutes_per_km=analytics["pace_minutes_per_km"],
                pace_display=analytics["pace_display"],
                slope_percent=analytics["slope_percent"],
            ),
            intervals=analytics["intervals"],
            zone_summary=analytics["zone_summary"],
            compliance=analytics["compliance"],
            zones=analytics["zones"],
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
