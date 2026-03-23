import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.auth.current_user import CurrentUserService
from app.domain.schemas.user import CurrentUserResponse
from app.domain.schemas.admin import AdminUserAuditItem, AdminUserListResponse
from app.infrastructure.repositories.user_repository import UserRepository


router = APIRouter(prefix="/admin")
logger = logging.getLogger(__name__)
ADMIN_STRAVA_ATHLETE_ID = 102168741


def _require_admin_user(request: Request, current_user_service: CurrentUserService) -> CurrentUserResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    if user.strava_athlete_id != ADMIN_STRAVA_ATHLETE_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user


@router.get("/users", response_model=AdminUserListResponse)
def list_users_for_admin(
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    db_session: Session = Depends(get_db_session),
) -> AdminUserListResponse:
    admin_user = _require_admin_user(request, current_user_service)
    logger.info("Listing users for admin.", extra={"user.id": admin_user.id})
    items = [AdminUserAuditItem.model_validate(user) for user in UserRepository(db_session).list_all()]
    return AdminUserListResponse(items=items)


@router.post("/users/{user_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
def disable_user(
    user_id: int,
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    db_session: Session = Depends(get_db_session),
) -> Response:
    admin_user = _require_admin_user(request, current_user_service)
    user_repository = UserRepository(db_session)
    target_user = user_repository.get_by_id(user_id)
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if target_user.strava_athlete_id == ADMIN_STRAVA_ATHLETE_ID:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="The admin account cannot be disabled.")
    if not target_user.is_active:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    target_user.is_active = False
    user_repository.save(target_user)
    db_session.commit()
    logger.info(
        "Disabled user from admin panel.",
        extra={"user.id": admin_user.id, "target_user.id": target_user.id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
