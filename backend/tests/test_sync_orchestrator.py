from app.application.sync.orchestrator import SyncOrchestrator
from app.infrastructure.db.models.sync_job import SyncJob


class SyncJobRepositoryStub:
    def __init__(self, latest_job=None) -> None:
        self.latest_job = latest_job
        self.saved = None

    def get_latest_for_user(self, _user_id: int):
        return self.latest_job

    def save(self, sync_job: SyncJob):
        sync_job.id = 10
        self.saved = sync_job
        return sync_job


class QueueClientStub:
    def __init__(self) -> None:
        self.enqueued = None

    def enqueue_full_import(self, *, sync_job_id: int, user_id: int) -> None:
        self.enqueued = {"sync_job_id": sync_job_id, "user_id": user_id}


class SessionStub:
    def commit(self):
        return None

    def refresh(self, _value):
        return None


def test_enqueue_first_import_if_needed_creates_queued_job_and_dispatches() -> None:
    service = SyncOrchestrator(db_session=SessionStub(), queue_client=QueueClientStub())
    service.sync_job_repository = SyncJobRepositoryStub()

    created_job = service.enqueue_first_import_if_needed(1)

    assert created_job is not None
    assert created_job.id == 10
    assert created_job.status == "queued"
    assert service.sync_job_repository.saved is not None
    assert service.queue_client.enqueued == {"sync_job_id": 10, "user_id": 1}


def test_enqueue_first_import_if_needed_skips_when_job_already_exists() -> None:
    existing_job = SyncJob(user_id=1, status="queued", sync_type="full_import")
    service = SyncOrchestrator(db_session=SessionStub(), queue_client=QueueClientStub())
    service.sync_job_repository = SyncJobRepositoryStub(latest_job=existing_job)

    created_job = service.enqueue_first_import_if_needed(1)

    assert created_job is None
    assert service.queue_client.enqueued is None
