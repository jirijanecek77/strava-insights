from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.application.auth.current_user import CurrentUserService
from app.application.read_models.dashboard import DashboardReadService
from app.domain.schemas.dashboard import DashboardResponse, PeriodComparisonSchema, TrendsResponse


router = APIRouter()


def _require_user(request: Request, current_user_service: CurrentUserService):
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    request: Request,
    sport_type: str | None = Query(None),
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    dashboard_read_service: DashboardReadService = Depends(DashboardReadService),
) -> DashboardResponse:
    user = _require_user(request, current_user_service)
    return dashboard_read_service.get_dashboard(user.id, today=date.today(), sport_type=sport_type)


@router.get("/trends", response_model=TrendsResponse)
def get_trends(
    request: Request,
    period_type: str = Query(..., pattern="^(week|month|year)$"),
    sport_type: str | None = Query(None),
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    dashboard_read_service: DashboardReadService = Depends(DashboardReadService),
) -> TrendsResponse:
    user = _require_user(request, current_user_service)
    return dashboard_read_service.get_trends(user.id, period_type=period_type, sport_type=sport_type)


@router.get("/comparisons", response_model=list[PeriodComparisonSchema])
def get_comparisons(
    request: Request,
    period_type: str = Query(..., pattern="^(rolling_30d|week|month|year)$"),
    sport_type: str | None = Query(None),
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    dashboard_read_service: DashboardReadService = Depends(DashboardReadService),
) -> list[PeriodComparisonSchema]:
    user = _require_user(request, current_user_service)
    return dashboard_read_service.get_comparisons(user.id, period_type=period_type, today=date.today(), sport_type=sport_type)
