from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.application.auth.current_user import CurrentUserService
from app.domain.schemas.user import CurrentUserResponse


router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user_profile(
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
) -> CurrentUserResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return user
