from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.domain.schemas.sync import SyncStatusResponse
from app.infrastructure.repositories.sync_job_repository import SyncJobRepository


class SyncStatusService:
    def __init__(self, db_session: Session = Depends(get_db_session)) -> None:
        self.sync_job_repository = SyncJobRepository(db_session)

    def get_status_for_user(self, user_id: int) -> SyncStatusResponse:
        sync_job = self.sync_job_repository.get_latest_for_user(user_id)
        if sync_job is None:
            return SyncStatusResponse(status="idle")

        return SyncStatusResponse.model_validate(sync_job)
