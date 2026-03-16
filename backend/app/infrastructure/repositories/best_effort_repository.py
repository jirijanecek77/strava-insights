from sqlalchemy.orm import Session

from app.infrastructure.db.models.best_effort import BestEffort


class BestEffortRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_user(self, user_id: int, *, sport_type: str | None = None) -> list[BestEffort]:
        query = self.session.query(BestEffort).filter(BestEffort.user_id == user_id)
        if sport_type is not None:
            query = query.filter(BestEffort.sport_type == sport_type)
        return query.order_by(BestEffort.sport_type.asc(), BestEffort.distance_meters.asc()).all()
