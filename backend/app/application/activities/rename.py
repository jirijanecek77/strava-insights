from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.domain.schemas.activity import ActivityRenameResponse
from app.infrastructure.repositories.activity_repository import ActivityRepository


class ActivityRenameService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.session = db_session
        self.activities = ActivityRepository(db_session)

    def rename(
        self, user_id: int, activity_id: int, name: str
    ) -> ActivityRenameResponse | None:
        activity = self.activities.get_by_id_for_user(activity_id, user_id)
        if activity is None:
            return None
        activity.name = name
        self.activities.save(activity)
        self.session.commit()
        return ActivityRenameResponse(id=activity.id, name=activity.name)
