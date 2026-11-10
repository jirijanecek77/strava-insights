from sqlalchemy.orm import Session

from app.infrastructure.db.models.training_plan import (
    TrainingPlanDay,
    TrainingPlanRequest,
)


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
