from sqlalchemy.orm import Session

from app.infrastructure.db.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.query(User).filter(User.id == user_id).one_or_none()

    def get_by_external_user_id(self, external_user_id: str, provider: str = "garmin") -> User | None:
        return (
            self.session.query(User)
            .filter(User.external_user_id == external_user_id, User.source_provider == provider)
            .one_or_none()
        )

    def list_all(self) -> list[User]:
        return (
            self.session.query(User)
            .order_by(User.last_login_at.desc().nullslast(), User.created_at.desc())
            .all()
        )

    def save(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user
