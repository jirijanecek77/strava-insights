from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.domain.schemas.training_plan import TrainingPlanItem, TrainingPlanResponse
from app.infrastructure.repositories.training_plan_repository import (
    TrainingPlanRepository,
)


class TrainingPlanReadService:
    def __init__(self, session: Session = Depends(get_db_session)):
        self.repository = TrainingPlanRepository(session)

    def list_plans(self, user_id, *, date_from, date_to):
        request = self.repository.latest_request(user_id)
        days = self.repository.list_days(user_id, date_from=date_from, date_to=date_to)
        today = datetime.now(ZoneInfo(request.timezone)).date() if request else None
        return TrainingPlanResponse(
            items=[
                TrainingPlanItem(
                    planned_date=d.planned_date,
                    kind=d.kind,
                    focus=d.focus,
                    distance_km=(
                        float(d.distance_meters) / 1000
                        if d.distance_meters is not None
                        else None
                    ),
                    pace_seconds_per_km=d.pace_seconds_per_km,
                    heart_rate_bpm=d.heart_rate_bpm,
                    rationale=d.rationale,
                    generated_at=d.generated_at,
                    request_id=d.request_id,
                    stale=bool(
                        request and d.request_id < request.id and d.planned_date > today
                    ),
                )
                for d in days
            ],
            status=request.status if request else "not_requested",
            timezone=request.timezone if request else None,
            window_start=request.target_start if request else None,
            window_end=(
                request.target_start + timedelta(days=6)
                if request and request.target_start
                else None
            ),
            generated_at=request.generated_at if request else None,
            message=request.last_error if request else None,
            weekly_objective=(
                (request.context_json or {}).get("weekly_objective")
                if request
                else None
            ),
        )
