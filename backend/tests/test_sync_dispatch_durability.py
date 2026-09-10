from app.application.sync.orchestrator import SyncOrchestrator
from app.infrastructure.db.models.sync_job import SyncJob
from app.infrastructure.repositories.sync_dispatch_outbox_repository import (
    SyncDispatchOutboxRepository,
)
from app.infrastructure.repositories.sync_job_repository import SyncJobRepository
from sqlalchemy.orm import Session
from typing import cast


class SessionStub:
    def commit(self) -> None:
        return None

    def refresh(self, _value: object) -> None:
        return None


class SyncJobRepositoryStub:
    def __init__(self) -> None:
        self.saved: SyncJob | None = None

    def get_latest_for_user(self, _user_id: int) -> None:
        return None

    def save(self, sync_job: SyncJob) -> SyncJob:
        sync_job.id = 42
        self.saved = sync_job
        return sync_job


class PendingDispatchStore:
    def __init__(self) -> None:
        self.records: list[dict[str, object]] = []

    def record_sync_dispatch(
            self, *, sync_job_id: int, user_id: int, sync_type: str
    ) -> None:
        self.records.append(
            {
                "sync_job_id": sync_job_id,
                "user_id": user_id,
                "sync_type": sync_type,
                "status": "pending",
            }
        )


def test_first_import_remains_durably_pending_when_broker_is_unavailable() -> None:
    """An accepted first import must survive a broker outage for later dispatch."""
    pending_dispatches = PendingDispatchStore()
    service = SyncOrchestrator(db_session=cast(Session, SessionStub()))
    service.sync_job_repository = cast(SyncJobRepository, SyncJobRepositoryStub())
    service.dispatch_store = cast(SyncDispatchOutboxRepository, pending_dispatches)

    created_job = service.enqueue_first_import_if_needed(7)

    assert created_job is not None
    assert created_job.id == 42
    assert pending_dispatches.records == [
        {
            "sync_job_id": 42,
            "user_id": 7,
            "sync_type": "full_import",
            "status": "pending",
        }
    ]
