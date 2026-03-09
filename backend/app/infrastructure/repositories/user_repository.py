from sqlalchemy.orm import Session

from app.infrastructure.db.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.query(User).filter(User.id == user_id).one_or_none()

    def get_by_strava_athlete_id(self, athlete_id: int) -> User | None:
        return (
            self.session.query(User)
            .filter(User.strava_athlete_id == athlete_id)
            .one_or_none()
        )

    def save(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user
