from app.models import User
from app.tasks.sync import _handle_authentication_required, _set_task_log_user_name


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
