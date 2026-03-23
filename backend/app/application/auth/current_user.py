from fastapi import Depends
from fastapi import Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.domain.schemas.user import CurrentUserResponse
from app.infrastructure.repositories.user_repository import UserRepository


class CurrentUserService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.db_session = db_session if isinstance(db_session, Session) else None

    def get_current_user(self, request: Request) -> CurrentUserResponse | None:
        session_user = request.session.get("user")
        if not session_user:
            return None

        if self.db_session is None:
            return CurrentUserResponse.model_validate(session_user)

        persisted_user = UserRepository(self.db_session).get_by_id(session_user["id"])
        if persisted_user is None or not persisted_user.is_active:
            request.session.clear()
            return None

        return CurrentUserResponse.model_validate(persisted_user)
