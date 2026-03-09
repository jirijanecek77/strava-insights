from app.api.routes.auth import _build_state_serializer
from app.application.auth.current_user import CurrentUserService
from app.application.auth.dto import AuthenticatedUser
from app.application.auth.oauth import StravaOAuthService
from app.application.sync.dto import CreatedSyncJob
from app.application.sync.orchestrator import SyncOrchestrator
from app.application.sync.status import SyncStatusService
from app.domain.schemas.sync import SyncStatusResponse
from app.domain.schemas.user import CurrentUserResponse
from app.main import app


class CurrentUserServiceStub:
    def __init__(self, user: CurrentUserResponse | None) -> None:
        self.user = user

    def get_current_user(self, _request):
        return self.user


class SyncStatusServiceStub:
    def __init__(self, response: SyncStatusResponse) -> None:
        self.response = response

    def get_status_for_user(self, _user_id: int) -> SyncStatusResponse:
        return self.response


class OAuthServiceStub:
    def build_authorization_url(self, state: str) -> str:
        return f"https://example.com/oauth?state={state}"

    def authenticate_from_code(self, code: str) -> AuthenticatedUser:
        assert code == "valid-code"
        return AuthenticatedUser(
            id=1,
            strava_athlete_id=162181,
            display_name="Test Athlete",
            profile_picture_url=None,
        )


class SyncOrchestratorStub:
    def enqueue_incremental_sync(self, _user_id: int) -> CreatedSyncJob:
        return CreatedSyncJob(id=42, user_id=1, sync_type="incremental_sync", status="queued")


def test_me_requires_authentication(client) -> None:
    response = client.get("/me")

    assert response.status_code == 401


def test_me_returns_current_user_with_dependency_override(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(
            id=1,
            strava_athlete_id=162181,
            display_name="Test Athlete",
            profile_picture_url=None,
        )
    )
    try:
        response = client.get("/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["display_name"] == "Test Athlete"


def test_sync_status_returns_idle_shape_with_override(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(
            id=1,
            strava_athlete_id=162181,
            display_name="Test Athlete",
            profile_picture_url=None,
        )
    )
    app.dependency_overrides[SyncStatusService] = lambda: SyncStatusServiceStub(
        SyncStatusResponse(status="idle")
    )
    try:
        response = client.get("/sync/status")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "idle",
        "sync_type": None,
        "started_at": None,
        "finished_at": None,
        "progress_total": None,
        "progress_completed": None,
        "error_message": None,
    }


def test_sync_refresh_enqueues_incremental_job(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(
            id=1,
            strava_athlete_id=162181,
            display_name="Test Athlete",
            profile_picture_url=None,
        )
    )
    app.dependency_overrides[SyncOrchestrator] = lambda: SyncOrchestratorStub()
    try:
        response = client.post("/sync/refresh")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json() == {
        "id": 42,
        "user_id": 1,
        "sync_type": "incremental_sync",
        "status": "queued",
    }


def test_oauth_login_returns_authorization_url(client) -> None:
    app.dependency_overrides[StravaOAuthService] = lambda: OAuthServiceStub()
    try:
        response = client.get("/auth/strava/login")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["authorization_url"].startswith("https://example.com/oauth?state=")


def test_oauth_callback_rejects_invalid_state(client) -> None:
    response = client.get("/auth/strava/callback?code=valid-code&state=bad-state")

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid OAuth state."}


def test_oauth_logout_returns_no_content(client) -> None:
    response = client.post("/auth/logout")

    assert response.status_code == 204


def test_oauth_callback_sets_session_and_redirects(client) -> None:
    app.dependency_overrides[StravaOAuthService] = lambda: OAuthServiceStub()
    login_response = client.get("/auth/strava/login")
    state = login_response.json()["authorization_url"].split("state=")[1]
    serializer = _build_state_serializer()
    serializer.loads(state)

    try:
        response = client.get(f"/auth/strava/callback?code=valid-code&state={state}", follow_redirects=False)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 302
    assert response.headers["location"] == "http://localhost:5173"
