from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.application.auth.current_user import CurrentUserService
from app.application.read_models.activities import ActivityReadService
from app.domain.schemas.activity import ActivityDetailResponse, ActivityListResponse


router = APIRouter(prefix="/activities")


def _require_user(request: Request, current_user_service: CurrentUserService):
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


@router.get("", response_model=ActivityListResponse)
def list_activities(
    request: Request,
    sport_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    activity_read_service: ActivityReadService = Depends(ActivityReadService),
) -> ActivityListResponse:
    user = _require_user(request, current_user_service)
    return activity_read_service.list_activities(user.id, sport_type=sport_type, date_from=date_from, date_to=date_to)


@router.get("/{activity_id}", response_model=ActivityDetailResponse)
def get_activity_detail(
    activity_id: int,
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    activity_read_service: ActivityReadService = Depends(ActivityReadService),
) -> ActivityDetailResponse:
    user = _require_user(request, current_user_service)
    detail = activity_read_service.get_activity_detail(user.id, activity_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
    return detail
