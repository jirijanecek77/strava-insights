from app.infrastructure.db.models.sync_dispatch_outbox import SyncDispatchOutbox
from sqlalchemy.orm import Session


class SyncDispatchOutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_sync_dispatch(
            self, *, sync_job_id: int, user_id: int, sync_type: str
    ) -> SyncDispatchOutbox:
        dispatch = SyncDispatchOutbox(
            sync_job_id=sync_job_id,
            user_id=user_id,
            sync_type=sync_type,
            payload_json={"sync_job_id": sync_job_id, "user_id": user_id},
            status="pending",
        )
        self.session.add(dispatch)
        self.session.flush()
        return dispatch
