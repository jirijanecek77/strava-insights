from datetime import UTC, datetime
from decimal import Decimal

from app.application.auth.current_user import CurrentUserService
from app.infrastructure.db.models.activity import Activity
from app.main import app
from tests.test_read_endpoint_integration import CurrentUserServiceStub


def _seed(monkeypatch):
    from tests.read_mocks import mock_activity_repositories

    rows = [
        Activity(
            id=activity_id,
            user_id=user_id,
            source_activity_id=2000 + activity_id,
            source_provider="garmin",
            name="Garmin Name",
            sport_type="Run",
            start_date_utc=datetime(2026, 9, 1, 6, tzinfo=UTC),
            start_date_local=datetime(2026, 9, 1, 8, tzinfo=UTC),
            distance_meters=Decimal("10000"),
            moving_time_seconds=2700,
        )
        for activity_id, user_id in ((11, 1), (12, 2))
    ]
    return rows, mock_activity_repositories(monkeypatch, rows)


def test_rename_activity_persists_custom_name(client, db_session, monkeypatch) -> None:
    rows, repositories = _seed(monkeypatch)
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    try:
        response = client.patch(
            "/activities/11", json={"name": "  Tempo by the river  "}
        )
        assert response.status_code == 200
        assert response.json() == {"id": 11, "name": "Tempo by the river"}

        assert client.get("/activities/11").json()["name"] == "Tempo by the river"
        repositories.activities.save.assert_called_once_with(rows[0])
        db_session.commit.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_rename_activity_rejects_blank_and_foreign_activities(
        client, db_session, monkeypatch
) -> None:
    rows, repositories = _seed(monkeypatch)
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    try:
        assert client.patch("/activities/11", json={"name": "   "}).status_code == 422
        assert (
                client.patch("/activities/11", json={"name": "x" * 256}).status_code == 422
        )
        assert (
                client.patch("/activities/12", json={"name": "Not mine"}).status_code == 404
        )
        assert rows[1].name == "Garmin Name"
    finally:
        app.dependency_overrides.clear()


def test_rename_activity_requires_authentication(client) -> None:
    class AnonymousUserService:
        def get_current_user(self, _request):
            return None

    app.dependency_overrides[CurrentUserService] = lambda: AnonymousUserService()
    try:
        assert client.patch("/activities/11", json={"name": "Name"}).status_code == 401
    finally:
        app.dependency_overrides.clear()
