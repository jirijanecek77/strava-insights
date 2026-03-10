from datetime import date

from sqlalchemy.orm import Session

from app.infrastructure.db.models.activity import Activity


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
