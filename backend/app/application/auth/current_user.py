from fastapi import Request

from app.domain.schemas.user import CurrentUserResponse


class CurrentUserService:
    def get_current_user(self, request: Request) -> CurrentUserResponse | None:
        session_user = request.session.get("user")
        if not session_user:
            return None

        return CurrentUserResponse.model_validate(session_user)
