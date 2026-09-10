import pytest
from app.models import User
from app.tasks.sync import (
    _handle_authentication_required,
    _set_task_log_user_name,
    run_incremental_sync,
)


class UserRepositoryStub:
    def __init__(self, _session) -> None:
        pass

    def get_by_id(self, user_id: int):
        return User(id=user_id, display_name="Test Athlete", is_active=True)


def test_set_task_log_user_name_uses_worker_user_display_name(monkeypatch) -> None:
    captured_user_names: list[str | None] = []

    def set_log_user_name_stub(user_name: str | None):
        captured_user_names.append(user_name)
        return "token"

    monkeypatch.setattr("app.tasks.sync.UserRepository", UserRepositoryStub)
    monkeypatch.setattr("app.tasks.sync.set_log_user_name", set_log_user_name_stub)

    token = _set_task_log_user_name(object(), 1)

    assert token == "token"
    assert captured_user_names == ["Test Athlete"]


def test_authentication_failure_marks_job_and_credential_without_reraising(monkeypatch) -> None:
    events: list[str] = []

    class SessionStub:
        def commit(self) -> None:
            events.append("commit")

    class SyncJobRepositoryStub:
        def get(self, sync_job_id: int, user_id: int):
            assert (sync_job_id, user_id) == (7, 1)
            return "job"

        def require_authentication(self, sync_job) -> None:
            assert sync_job == "job"
            events.append("job")

    class GarminCredentialRepositoryStub:
        def __init__(self, _session) -> None:
            pass

        def mark_reauthentication_required(self, user_id: int) -> None:
            assert user_id == 1
            events.append("credential")

    monkeypatch.setattr("app.tasks.sync.GarminCredentialRepository", GarminCredentialRepositoryStub)

    _handle_authentication_required(SessionStub(), SyncJobRepositoryStub(), sync_job_id=7, user_id=1)

    assert events == ["job", "credential", "commit"]


def test_incremental_task_ignores_duplicate_delivery_after_a_job_has_started(
        monkeypatch,
) -> None:
    class SessionStub:
        def close(self) -> None:
            return None

    class SyncJobRepositoryStub:
        def __init__(self, _session) -> None:
            pass

        def claim_for_execution(self, *, sync_job_id: int, user_id: int):
            assert (sync_job_id, user_id) == (7, 1)
            return None

    class IncrementalSyncServiceStub:
        def __init__(self, _session) -> None:
            raise AssertionError("A duplicate task must not start another import.")

    monkeypatch.setattr("app.tasks.sync.SessionLocal", lambda: SessionStub())
    monkeypatch.setattr("app.tasks.sync.SyncJobRepository", SyncJobRepositoryStub)
    monkeypatch.setattr("app.tasks.sync._set_task_log_user_name", lambda *_args: "token")
    monkeypatch.setattr("app.tasks.sync.reset_log_user_name", lambda _token: None)
    monkeypatch.setattr(
        "app.tasks.sync.IncrementalSyncService", IncrementalSyncServiceStub
    )

    run_incremental_sync.run(sync_job_id=7, user_id=1)


def test_incremental_task_retries_a_transient_import_failure(monkeypatch) -> None:
    retry_calls: list[dict[str, object]] = []

    class RetryRequested(Exception):
        pass

    class SessionStub:
        def rollback(self) -> None:
            return None

        def commit(self) -> None:
            return None

        def close(self) -> None:
            return None

    class SyncJobRepositoryStub:
        def __init__(self, _session) -> None:
            pass

        def claim_for_execution(self, *, sync_job_id: int, user_id: int):
            assert (sync_job_id, user_id) == (7, 1)
            return "job"

        def get(self, sync_job_id: int, user_id: int):
            assert (sync_job_id, user_id) == (7, 1)
            return "job"

        def requeue_after_transient_failure(self, sync_job, *, error_message: str) -> None:
            assert sync_job == "job"
            assert error_message == "Garmin is temporarily unavailable"

    class IncrementalSyncServiceStub:
        def __init__(self, _session) -> None:
            pass

        def run(self, *, sync_job_id: int, user_id: int) -> None:
            assert (sync_job_id, user_id) == (7, 1)
            raise RuntimeError("Garmin is temporarily unavailable")

    def retry(*, exc: Exception, countdown: int, max_retries: int) -> None:
        retry_calls.append(
            {"error": str(exc), "countdown": countdown, "max_retries": max_retries}
        )
        raise RetryRequested()

    monkeypatch.setattr("app.tasks.sync.SessionLocal", lambda: SessionStub())
    monkeypatch.setattr("app.tasks.sync.SyncJobRepository", SyncJobRepositoryStub)
    monkeypatch.setattr("app.tasks.sync._set_task_log_user_name", lambda *_args: "token")
    monkeypatch.setattr("app.tasks.sync.reset_log_user_name", lambda _token: None)
    monkeypatch.setattr(
        "app.tasks.sync.IncrementalSyncService", IncrementalSyncServiceStub
    )
    monkeypatch.setattr(run_incremental_sync, "retry", retry)

    with pytest.raises(RetryRequested):
        run_incremental_sync.run(sync_job_id=7, user_id=1)

    assert retry_calls == [
        {
            "error": "Garmin is temporarily unavailable",
            "countdown": 2,
            "max_retries": 3,
        }
    ]
