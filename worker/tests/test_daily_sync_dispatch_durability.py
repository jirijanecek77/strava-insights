from app.services.sync_scheduler import DailyIncrementalSyncScheduler
from sqlalchemy.orm import Session
from typing import Any, cast


class SessionStub:
    def commit(self) -> None:
        return None


class SyncJobStub:
    def __init__(self, job_id: int, user_id: int) -> None:
        self.id = job_id
        self.user_id = user_id
        self.status = "queued"
        self.sync_type = "incremental_sync"


class SyncJobRepositoryStub:
    def get_active_for_user(self, _user_id: int) -> None:
        return None

    def create_queued(
            self, *, user_id: int, sync_type: str, metadata_json: dict | None = None
    ) -> SyncJobStub:
        assert sync_type == "incremental_sync"
        assert metadata_json == {"source": "daily_schedule"}
        return SyncJobStub(job_id=91, user_id=user_id)


class PendingDispatchStore:
    def __init__(self) -> None:
        self.records: list[tuple[int, int, str]] = []

    def record_sync_dispatch(
            self, *, sync_job_id: int, user_id: int, sync_type: str
    ) -> None:
        self.records.append((sync_job_id, user_id, sync_type))


def test_daily_schedule_persists_dispatch_without_requiring_the_broker() -> None:
    scheduler = cast(
        Any, DailyIncrementalSyncScheduler(cast(Session, SessionStub()))
    )
    scheduler.users = type(
        "UserRepositoryStub", (), {"list_incremental_sync_candidates": lambda _self: [7]}
    )()
    scheduler.sync_jobs = SyncJobRepositoryStub()
    pending_dispatches = PendingDispatchStore()
    scheduler.dispatch_store = pending_dispatches

    assert scheduler.run() == 1
    assert pending_dispatches.records == [(91, 7, "incremental_sync")]
