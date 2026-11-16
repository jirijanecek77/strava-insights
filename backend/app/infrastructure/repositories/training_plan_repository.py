from app.infrastructure.db.models.activity import Activity
from app.infrastructure.db.models.training_plan import (
    TrainingPlanDay,
    TrainingPlanRequest,
)
from datetime import date
from sqlalchemy import Date, cast
from sqlalchemy.orm import Session


class TrainingPlanRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_days(self, user_id, *, date_from, date_to):
        return (
            self.session.query(TrainingPlanDay)
            .filter(
                TrainingPlanDay.user_id == user_id,
                TrainingPlanDay.planned_date >= date_from,
                TrainingPlanDay.planned_date <= date_to,
            )
            .order_by(TrainingPlanDay.planned_date)
            .all()
        )

    def latest_request(self, user_id):
        return (
            self.session.query(TrainingPlanRequest)
            .filter(TrainingPlanRequest.user_id == user_id)
            .order_by(TrainingPlanRequest.id.desc())
            .first()
        )

    def completed_activity_dates(
            self, user_id: int, *, date_from: date, date_to: date
    ) -> set[date]:
        local_day = cast(Activity.start_date_local, Date)
        rows = (
            self.session.query(local_day)
            .filter(
                Activity.user_id == user_id,
                local_day >= date_from,
                local_day <= date_to,
            )
            .distinct()
            .all()
        )
        return {activity_date for (activity_date,) in rows}
