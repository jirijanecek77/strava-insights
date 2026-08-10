from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.read_models.effort_rankings import rank_best_efforts
from app.domain.schemas.best_effort import BestEffortItem, BestEffortsResponse
from app.infrastructure.repositories.best_effort_repository import BestEffortRepository


class BestEffortReadService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.best_efforts = BestEffortRepository(db_session)

    def list_best_efforts(
        self, user_id: int, *, sport_type: str | None = None
    ) -> BestEffortsResponse:
        items = self.best_efforts.list_for_user(user_id, sport_type=sport_type)
        return BestEffortsResponse(
            items=[
                BestEffortItem(
                    sport_type=item.effort.sport_type,
                    effort_code=item.effort.effort_code,
                    best_time_seconds=item.effort.best_time_seconds,
                    distance_meters=item.effort.distance_meters,
                    activity_id=item.effort.activity_id,
                    achieved_at=item.effort.achieved_at,
                    rank=item.rank,
                    pace_seconds_per_km=item.pace_seconds_per_km,
                    average_speed_kph=item.average_speed_kph,
                )
                for item in rank_best_efforts(items)
            ]
        )
