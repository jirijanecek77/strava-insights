from app.models import User
from app.tasks.sync import _set_task_log_user_name


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
