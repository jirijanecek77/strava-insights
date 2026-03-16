from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.application.auth.current_user import CurrentUserService
from app.application.read_models.best_efforts import BestEffortReadService
from app.domain.schemas.best_effort import BestEffortsResponse


router = APIRouter(prefix="/best-efforts")


@router.get("", response_model=BestEffortsResponse)
def list_best_efforts(
    request: Request,
    sport_type: str | None = Query(None),
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    best_effort_read_service: BestEffortReadService = Depends(BestEffortReadService),
) -> BestEffortsResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return best_effort_read_service.list_best_efforts(user.id, sport_type=sport_type)
