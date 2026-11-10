from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.application.auth.current_user import CurrentUserService
from app.application.read_models.training_plans import TrainingPlanReadService
from app.domain.schemas.training_plan import TrainingPlanResponse

router = APIRouter(prefix="/training-plans")


@router.get("", response_model=TrainingPlanResponse)
def list_training_plans(
    request: Request,
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    read_service: TrainingPlanReadService = Depends(TrainingPlanReadService),
):
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(
            status_code=422, detail="Provide an ordered date range of at most 367 days."
        )
    return read_service.list_plans(user.id, date_from=date_from, date_to=date_to)
