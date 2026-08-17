from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infrastructure.db.models.activity import Activity
from app.infrastructure.db.models.local_route import (
    ActivityRouteMembership,
    RouteGroup,
)


@dataclass(frozen=True, slots=True)
class RouteAttemptGroup:
    id: int
    sport_type: str
    nominal_distance_meters: Decimal
    activities: list[Activity]


class ActivityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id_for_user(self, activity_id: int, user_id: int) -> Activity | None:
        return (
            self.session.query(Activity)
            .filter(Activity.id == activity_id, Activity.user_id == user_id)
            .one_or_none()
        )

    def list_for_user(
        self,
        user_id: int,
        *,
        sport_type: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[Activity]:
        query = self.session.query(Activity).filter(Activity.user_id == user_id)
        if sport_type is not None:
            query = query.filter(Activity.sport_type == sport_type)
        if date_from is not None:
            query = query.filter(Activity.start_date_local >= date_from)
        if date_to is not None:
            query = query.filter(Activity.start_date_local < date_to)
        return query.order_by(Activity.start_date_local.desc()).all()

    def list_with_hr_and_speed(
        self, user_id: int, *, sport_type: str | None = None
    ) -> list[Activity]:
        query = self.session.query(Activity).filter(
            Activity.user_id == user_id,
            Activity.average_heartrate_bpm.isnot(None),
            Activity.average_speed_mps.isnot(None),
        )
        if sport_type is not None:
            query = query.filter(Activity.sport_type == sport_type)
        return query.order_by(Activity.start_date_local.asc()).all()

    def get_route_attempt_group(
        self, user_id: int, activity_id: int
    ) -> RouteAttemptGroup | None:
        group = (
            self.session.query(RouteGroup)
            .join(
                ActivityRouteMembership,
                ActivityRouteMembership.route_group_id == RouteGroup.id,
            )
            .filter(
                ActivityRouteMembership.activity_id == activity_id,
                RouteGroup.user_id == user_id,
            )
            .one_or_none()
        )
        if group is None:
            return None

        activities = (
            self.session.query(Activity)
            .join(
                ActivityRouteMembership,
                ActivityRouteMembership.activity_id == Activity.id,
            )
            .filter(
                Activity.user_id == user_id,
                ActivityRouteMembership.route_group_id == group.id,
            )
            .order_by(
                Activity.moving_time_seconds.asc(), Activity.start_date_local.asc()
            )
            .all()
        )
        return RouteAttemptGroup(
            id=group.id,
            sport_type=group.sport_type,
            nominal_distance_meters=group.nominal_distance_meters,
            activities=activities,
        )
