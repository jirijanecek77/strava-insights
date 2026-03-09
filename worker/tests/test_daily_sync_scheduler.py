from app.services.sync_scheduler import DailyIncrementalSyncScheduler


class SessionStub:
    def __init__(self) -> None:
        self.flushes = 0

    def flush(self) -> None:
        self.flushes += 1


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


class CeleryAppStub:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send_task(self, name: str, kwargs: dict) -> None:
        self.calls.append({"name": name, "kwargs": kwargs})


def test_daily_scheduler_creates_jobs_for_users_without_active_sync(monkeypatch) -> None:
    session = SessionStub()
    scheduler = DailyIncrementalSyncScheduler(session)
    scheduler.users = UserRepositoryStub([1, 2, 3])
    scheduler.sync_jobs = SyncJobRepositoryStub({1: None, 2: SyncJobStub(7, 2, status="running"), 3: None})
    celery_app_stub = CeleryAppStub()
    monkeypatch.setattr("app.services.sync_scheduler.celery_app", celery_app_stub)

    scheduled_jobs = scheduler.run()

    assert scheduled_jobs == 2
    assert [job.user_id for job in scheduler.sync_jobs.created_jobs] == [1, 3]
    assert celery_app_stub.calls == [
        {
            "name": "app.tasks.sync.run_incremental_sync",
            "kwargs": {"sync_job_id": 101, "user_id": 1},
        },
        {
            "name": "app.tasks.sync.run_incremental_sync",
            "kwargs": {"sync_job_id": 102, "user_id": 3},
        },
    ]


def test_daily_scheduler_returns_zero_when_all_users_have_active_jobs(monkeypatch) -> None:
    session = SessionStub()
    scheduler = DailyIncrementalSyncScheduler(session)
    scheduler.users = UserRepositoryStub([1, 2])
    scheduler.sync_jobs = SyncJobRepositoryStub(
        {1: SyncJobStub(5, 1, status="queued"), 2: SyncJobStub(6, 2, status="running")}
    )
    celery_app_stub = CeleryAppStub()
    monkeypatch.setattr("app.services.sync_scheduler.celery_app", celery_app_stub)

    scheduled_jobs = scheduler.run()

    assert scheduled_jobs == 0
    assert scheduler.sync_jobs.created_jobs == []
    assert celery_app_stub.calls == []
