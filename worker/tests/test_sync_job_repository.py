from app.models import SyncJob
from app.repositories import SyncJobRepository
from sqlalchemy.orm import Session
from typing import Any, cast


class QueryStub:
    def filter(self, *_conditions):
        return self

    def update(self, _values, *, synchronize_session: bool) -> int:
        assert synchronize_session is False
        return 1


class SessionStub:
    def __init__(self) -> None:
        self.committed = False

    def query(self, _model) -> QueryStub:
        return QueryStub()

    def commit(self) -> None:
        self.committed = True


def test_claim_for_execution_marks_a_queued_job_running_before_import() -> None:
    session = SessionStub()
    repository = SyncJobRepository(cast(Session, session))
    claimed_job = SyncJob(user_id=7, status="running", sync_type="incremental_sync")
    cast(Any, repository).get = lambda _sync_job_id, _user_id: claimed_job

    assert repository.claim_for_execution(sync_job_id=42, user_id=7) is claimed_job
    assert session.committed is True
