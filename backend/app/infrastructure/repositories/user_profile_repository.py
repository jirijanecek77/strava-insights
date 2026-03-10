from sqlalchemy.orm import Session

from app.infrastructure.db.models.user_profile import UserProfile


class UserProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> UserProfile | None:
        return self.session.query(UserProfile).filter(UserProfile.user_id == user_id).one_or_none()
