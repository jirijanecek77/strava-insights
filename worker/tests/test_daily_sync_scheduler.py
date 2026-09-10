import logging
from app.services.sync_scheduler import DailyIncrementalSyncScheduler
from sqlalchemy.orm import Session
from typing import Any, cast


class SessionStub:
    def __init__(self) -> None:
        self.flushes = 0
        self.commits = 0

    def flush(self) -> None:
        self.flushes += 1

    def commit(self) -> None:
        self.commits += 1


class UserRepositoryStub:
    def __init__(self, user_ids: list[int]) -> None:
        self.user_ids = user_ids

    def list_incremental_sync_candidates(self) -> list[int]:
        return self.user_ids


class SyncJobStub:
    def __init__(self, job_id: int, user_id: int, status: str = "queued", sync_type: str = "incremental_sync") -> None:
        self.id = job_id
        self.user_id = user_id
        self.status = status
        self.sync_type = sync_type
        self.metadata_json: dict | None = None


class SyncJobRepositoryStub:
    def __init__(self, active_by_user: dict[int, SyncJobStub | None]) -> None:
        self.active_by_user = active_by_user
        self.created_jobs: list[SyncJobStub] = []
        self.counter = 100

    def get_active_for_user(self, user_id: int):
        return self.active_by_user.get(user_id)

    def create_queued(self, *, user_id: int, sync_type: str, metadata_json: dict | None = None) -> SyncJobStub:
        self.counter += 1
        sync_job = SyncJobStub(job_id=self.counter, user_id=user_id, sync_type=sync_type)
        sync_job.metadata_json = metadata_json
        self.created_jobs.append(sync_job)
        return sync_job


class SyncDispatchStoreStub:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record_sync_dispatch(
            self, *, sync_job_id: int, user_id: int, sync_type: str
    ) -> None:
        self.records.append(
            {
                "sync_job_id": sync_job_id,
                "user_id": user_id,
                "sync_type": sync_type,
            }
        )


def test_daily_scheduler_creates_jobs_for_users_without_active_sync() -> None:
    session = SessionStub()
    scheduler = cast(
        Any, DailyIncrementalSyncScheduler(cast(Session, session))
    )
    scheduler.users = UserRepositoryStub([1, 2, 3])
    scheduler.sync_jobs = SyncJobRepositoryStub({1: None, 2: SyncJobStub(7, 2, status="running"), 3: None})
    dispatch_store = SyncDispatchStoreStub()
    scheduler.dispatch_store = dispatch_store

    scheduled_jobs = scheduler.run()

    assert scheduled_jobs == 2
    assert [job.user_id for job in scheduler.sync_jobs.created_jobs] == [1, 3]
    assert dispatch_store.records == [
        {
            "sync_job_id": 101,
            "user_id": 1,
            "sync_type": "incremental_sync",
        },
        {
            "sync_job_id": 102,
            "user_id": 3,
            "sync_type": "incremental_sync",
        },
    ]
    assert session.commits == 2


def test_daily_scheduler_returns_zero_when_all_users_have_active_jobs() -> None:
    session = SessionStub()
    scheduler = cast(
        Any, DailyIncrementalSyncScheduler(cast(Session, session))
    )
    scheduler.users = UserRepositoryStub([1, 2])
    scheduler.sync_jobs = SyncJobRepositoryStub(
        {1: SyncJobStub(5, 1, status="queued"), 2: SyncJobStub(6, 2, status="running")}
    )
    dispatch_store = SyncDispatchStoreStub()
    scheduler.dispatch_store = dispatch_store

    scheduled_jobs = scheduler.run()

    assert scheduled_jobs == 0
    assert scheduler.sync_jobs.created_jobs == []
    assert dispatch_store.records == []


def test_daily_scheduler_logs_candidate_and_skip_counts(caplog) -> None:
    session = SessionStub()
    scheduler = cast(
        Any, DailyIncrementalSyncScheduler(cast(Session, session))
    )
    scheduler.users = UserRepositoryStub([1, 2])
    scheduler.sync_jobs = SyncJobRepositoryStub(
        {1: SyncJobStub(5, 1, status="queued"), 2: None}
    )
    scheduler.dispatch_store = SyncDispatchStoreStub()
    caplog.set_level(logging.INFO)

    scheduled_jobs = scheduler.run()

    assert scheduled_jobs == 1
    assert any("Loaded incremental sync candidates." in message for message in caplog.messages)
    assert any("Skipping scheduled sync because an active job exists." in message for message in caplog.messages)


def test_daily_scheduler_commits_job_and_dispatch_record_together() -> None:
    events: list[str] = []

    class SyncJobRepositoryWithEvents(SyncJobRepositoryStub):
        def create_queued(self, *, user_id: int, sync_type: str, metadata_json: dict | None = None) -> SyncJobStub:
            events.append("create")
            return super().create_queued(user_id=user_id, sync_type=sync_type, metadata_json=metadata_json)

    class SyncDispatchStoreWithEvents(SyncDispatchStoreStub):
        def record_sync_dispatch(
                self, *, sync_job_id: int, user_id: int, sync_type: str
        ) -> None:
            events.append("record")
            super().record_sync_dispatch(
                sync_job_id=sync_job_id, user_id=user_id, sync_type=sync_type
            )

    class SessionWithEvents(SessionStub):
        def commit(self) -> None:
            super().commit()
            events.append("commit")

    session = SessionWithEvents()
    scheduler = cast(
        Any, DailyIncrementalSyncScheduler(cast(Session, session))
    )
    scheduler.users = UserRepositoryStub([1])
    scheduler.sync_jobs = SyncJobRepositoryWithEvents({1: None})
    scheduler.dispatch_store = SyncDispatchStoreWithEvents()

    scheduled_jobs = scheduler.run()

    assert scheduled_jobs == 1
    assert events == ["create", "record", "commit"]
