from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.application.auth.current_user import CurrentUserService
from app.application.coaching.read import CoachingReadService
from app.domain.schemas.coaching import PeriodCoachingResponse

router = APIRouter(prefix="/coaching")


@router.get("/periods", response_model=PeriodCoachingResponse)
def list_period_coaching(
    request: Request,
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    coaching_read_service: CoachingReadService = Depends(CoachingReadService),
) -> PeriodCoachingResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required."
        )
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_to must not be before date_from.",
        )
    return coaching_read_service.list_periods(
        user.id, date_from=date_from, date_to=date_to
    )
