from app.application.auth.current_user import CurrentUserService
from app.infrastructure.db.models.activity import Activity
from app.infrastructure.db.models.user import User
from app.main import app
from datetime import UTC, datetime
from decimal import Decimal

from tests.test_read_endpoint_integration import CurrentUserServiceStub


def _seed(db_session) -> None:
    for user_id in (1, 2):
        db_session.add(
            User(
                id=user_id,
                external_user_id=f"ext-{user_id}",
                source_provider="garmin",
                display_name=f"Athlete {user_id}",
                profile_picture_url=None,
                is_active=True,
            )
        )
    db_session.flush()
    db_session.add_all(
        [
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
    )
    db_session.commit()


def test_rename_activity_persists_custom_name(client, db_session) -> None:
    _seed(db_session)
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    try:
        response = client.patch("/activities/11", json={"name": "  Tempo by the river  "})
        assert response.status_code == 200
        assert response.json() == {"id": 11, "name": "Tempo by the river"}

        assert client.get("/activities/11").json()["name"] == "Tempo by the river"
    finally:
        app.dependency_overrides.clear()


def test_rename_activity_rejects_blank_and_foreign_activities(client, db_session) -> None:
    _seed(db_session)
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    try:
        assert client.patch("/activities/11", json={"name": "   "}).status_code == 422
        assert client.patch("/activities/11", json={"name": "x" * 256}).status_code == 422
        assert client.patch("/activities/12", json={"name": "Not mine"}).status_code == 404
        db_session.expire_all()
        assert db_session.get(Activity, 12).name == "Garmin Name"
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
