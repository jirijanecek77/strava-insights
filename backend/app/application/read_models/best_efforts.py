from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.domain.schemas.best_effort import BestEffortItem, BestEffortsResponse
from app.infrastructure.repositories.best_effort_repository import BestEffortRepository


class BestEffortReadService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.best_efforts = BestEffortRepository(db_session)

    def list_best_efforts(self, user_id: int, *, sport_type: str | None = None) -> BestEffortsResponse:
        items = self.best_efforts.list_for_user(user_id, sport_type=sport_type)
        return BestEffortsResponse(items=[BestEffortItem.model_validate(item, from_attributes=True) for item in items])
