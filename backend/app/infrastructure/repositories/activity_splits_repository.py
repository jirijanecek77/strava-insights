from sqlalchemy.orm import Session

from app.infrastructure.db.models.activity_splits import ActivitySplits


class ActivitySplitsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_for_activity(self, activity_id: int) -> ActivitySplits | None:
        return self.session.get(ActivitySplits, activity_id)
