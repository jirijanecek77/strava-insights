import pytest
from app.application.sync.orchestrator import SyncOrchestrator
from app.infrastructure.db.models.garmin_credential import GarminCredential
from app.infrastructure.db.models.sync_job import SyncJob
from app.infrastructure.repositories.sync_dispatch_outbox_repository import (
    SyncDispatchOutboxRepository,
)
from app.infrastructure.repositories.sync_job_repository import SyncJobRepository
from fastapi import HTTPException
from sqlalchemy.orm import Session
from typing import cast


class SyncJobRepositoryStub:
    def __init__(self, latest_job: SyncJob | None = None) -> None:
        self.latest_job = latest_job
        self.saved: SyncJob | None = None

    def get_latest_for_user(self, _user_id: int) -> SyncJob | None:
        return self.latest_job

    def save(self, sync_job: SyncJob) -> SyncJob:
        sync_job.id = 10
        self.saved = sync_job
        return sync_job


class SyncDispatchStoreStub:
    def __init__(self) -> None:
        self.recorded: dict[str, int | str] | None = None

    def record_sync_dispatch(
            self, *, sync_job_id: int, user_id: int, sync_type: str
    ) -> None:
        self.recorded = {
            "sync_job_id": sync_job_id,
            "user_id": user_id,
            "sync_type": sync_type,
        }


class SessionStub:
    def commit(self):
        return None

    def refresh(self, _value):
        return None


def test_enqueue_first_import_if_needed_creates_queued_job_and_persists_dispatch() -> None:
    dispatch_store = SyncDispatchStoreStub()
    repository = SyncJobRepositoryStub()
    service = SyncOrchestrator(db_session=cast(Session, SessionStub()))
    service.sync_job_repository = cast(SyncJobRepository, repository)
    service.dispatch_store = cast(SyncDispatchOutboxRepository, dispatch_store)

    created_job = service.enqueue_first_import_if_needed(1)

    assert created_job is not None
    assert created_job.id == 10
    assert created_job.status == "queued"
    assert repository.saved is not None
    assert dispatch_store.recorded == {
        "sync_job_id": 10,
        "user_id": 1,
        "sync_type": "full_import",
    }


def test_enqueue_first_import_if_needed_skips_when_job_already_exists() -> None:
    existing_job = SyncJob(user_id=1, status="queued", sync_type="full_import")
    dispatch_store = SyncDispatchStoreStub()
    repository = SyncJobRepositoryStub(latest_job=existing_job)
    service = SyncOrchestrator(db_session=cast(Session, SessionStub()))
    service.sync_job_repository = cast(SyncJobRepository, repository)
    service.dispatch_store = cast(SyncDispatchOutboxRepository, dispatch_store)

    created_job = service.enqueue_first_import_if_needed(1)

    assert created_job is None
    assert dispatch_store.recorded is None


def test_manual_sync_requires_a_connected_garmin_credential() -> None:
    service = SyncOrchestrator(db_session=cast(Session, SessionStub()))
    service.garmin_credentials = type(
        "CredentialRepositoryStub",
        (),
        {
            "get_for_user": lambda _self, _user_id: GarminCredential(
                user_id=1,
                email_encrypted="encrypted-email",
                token_json_encrypted="encrypted-token",
                external_user_id="athlete",
                connection_status="reauthentication_required",
            )
        },
    )()

    with pytest.raises(HTTPException, match="Reconnect Garmin") as error:
        service.enqueue_incremental_sync(1)

    assert error.value.status_code == 409
