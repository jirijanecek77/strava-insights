from sqlalchemy.orm import Session

from app.infrastructure.db.models.activity_stream import ActivityStream


class ActivityStreamRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_activity(self, activity_id: int) -> ActivityStream | None:
        return self.session.query(ActivityStream).filter(ActivityStream.activity_id == activity_id).one_or_none()
