"""PostgreSQL date predicates shared by planning and activity-note claims."""

from app.models import Activity
from sqlalchemy import Date, and_, cast, func
from sqlalchemy.sql.elements import ColumnElement


def recent_planning_activity(timezone) -> ColumnElement[bool]:
    local_date = cast(
        func.coalesce(
            Activity.start_date_local, func.timezone(timezone, Activity.start_date_utc)
        ),
        Date,
    )
    today = cast(func.timezone(timezone, func.now()), Date)
    return and_(
        Activity.sport_type.in_(["Run", "Ride", "EBikeRide"]),
        local_date >= today - 29,
        local_date <= today,
    )
