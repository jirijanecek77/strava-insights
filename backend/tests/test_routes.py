from app.api.routes.auth import _build_state_serializer
from app.application.auth.current_user import CurrentUserService
from app.application.auth.dto import AuthenticatedUser
from app.application.auth.oauth import StravaOAuthService
from app.application.read_models.activities import ActivityReadService
from app.application.read_models.best_efforts import BestEffortReadService
from app.application.read_models.dashboard import DashboardReadService
from app.application.sync.dto import CreatedSyncJob
from app.application.sync.orchestrator import SyncOrchestrator
from app.application.sync.status import SyncStatusService
from app.domain.schemas.activity import ActivityDetailResponse, ActivityKpis, ActivityListResponse, ActivityListRow, ActivityMap, ActivitySeries
from app.domain.schemas.best_effort import BestEffortItem, BestEffortsResponse
from app.domain.schemas.dashboard import DashboardResponse, PeriodComparisonSchema, PeriodSummarySchema, TrendsResponse
from app.domain.schemas.sync import SyncStatusResponse
from app.domain.schemas.user import CurrentUserResponse
from app.infrastructure.db.models.user import User
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


class DashboardReadServiceStub:
    def get_dashboard(self, _user_id: int, *, today, sport_type=None) -> DashboardResponse:
        period = PeriodSummarySchema(
            sport_type="Run",
            period_type="month",
            period_start=today.replace(day=1),
            activity_count=3,
            total_distance_meters="30000",
            total_moving_time_seconds=7200,
            average_speed_mps=None,
            average_pace_seconds_per_km="240.00",
            total_elevation_gain_meters="300.00",
            total_difficulty_score="4.0000",
        )
        comparison = PeriodComparisonSchema(current=period, previous=None)
        return DashboardResponse(month=[comparison], year=[comparison])

    def get_trends(self, _user_id: int, *, period_type: str, sport_type=None) -> TrendsResponse:
        return TrendsResponse(items=[], period_type=period_type)

    def get_comparisons(
        self,
        _user_id: int,
        *,
        period_type: str,
        today,
        current_period_start=None,
        previous_period_start=None,
        sport_type=None,
    ) -> list[PeriodComparisonSchema]:
        return []


class ActivityReadServiceStub:
    def list_activities(self, _user_id: int, **_kwargs) -> ActivityListResponse:
        return ActivityListResponse(
            items=[
                ActivityListRow(
                    id=5,
                    sport_type="Run",
                    name="Morning Run",
                    distance_km="10.00",
                    moving_time_display="45:00",
                    summary_metric_display="4:30",
                    summary_metric_kind="pace",
                    heart_rate_drift_bpm="3.00",
                )
            ]
        )

    def get_activity_detail(self, _user_id: int, activity_id: int) -> ActivityDetailResponse | None:
        if activity_id != 5:
            return None
        return ActivityDetailResponse(
            id=5,
            sport_type="Run",
            name="Morning Run",
            kpis=ActivityKpis(
                distance_km="10.00",
                moving_time_display="45:00",
                summary_metric_display="4:30",
                summary_metric_kind="pace",
                heart_rate_drift_bpm="3.00",
            ),
            map=ActivityMap(polyline=[[50.0, 14.0], [50.1, 14.1]], bounds={"min_lat": 50.0, "max_lat": 50.1, "min_lng": 14.0, "max_lng": 14.1}),
            series=ActivitySeries(
                distance_km=[0.0, 1.0],
                altitude_meters=[200.0, 202.0],
                moving_average_heartrate=[140.0, 145.0],
                moving_average_speed_kph=[12.0, 12.5],
                pace_minutes_per_km=[5.0, 4.8],
                pace_display=["5:00", "4:48"],
                slope_percent=[0.0, 1.0],
            ),
            intervals=[],
            zone_summary={},
            compliance=None,
            zones=[],
        )


class BestEffortReadServiceStub:
    def list_best_efforts(self, _user_id: int, *, sport_type=None) -> BestEffortsResponse:
        return BestEffortsResponse(items=[BestEffortItem(sport_type=sport_type or "Run", effort_code="5km", best_time_seconds=1400, distance_meters="5000")])


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


def test_me_profile_returns_empty_payload_when_profile_missing(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(
            id=1,
            strava_athlete_id=162181,
            display_name="Test Athlete",
            profile_picture_url=None,
        )
    )
    try:
        response = client.get("/me/profile")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "birthday": None,
        "speed_max": None,
        "max_heart_rate_override": None,
    }


def test_me_profile_can_be_updated(client, db_session) -> None:
    db_session.add(
        User(
            id=1,
            strava_athlete_id=162181,
            display_name="Test Athlete",
            profile_picture_url=None,
            is_active=True,
        )
    )
    db_session.commit()

    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(
            id=1,
            strava_athlete_id=162181,
            display_name="Test Athlete",
            profile_picture_url=None,
        )
    )
    try:
        response = client.put(
            "/me/profile",
            json={
                "birthday": "1990-01-01",
                "speed_max": "15.50",
                "max_heart_rate_override": None,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "birthday": "1990-01-01",
        "speed_max": "15.50",
        "max_heart_rate_override": None,
    }


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


def test_dashboard_returns_response_shape(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(id=1, strava_athlete_id=162181, display_name="Test Athlete", profile_picture_url=None)
    )
    app.dependency_overrides[DashboardReadService] = lambda: DashboardReadServiceStub()
    try:
        response = client.get("/dashboard")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["month"][0]["current"]["sport_type"] == "Run"


def test_trends_returns_response_shape(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(id=1, strava_athlete_id=162181, display_name="Test Athlete", profile_picture_url=None)
    )
    app.dependency_overrides[DashboardReadService] = lambda: DashboardReadServiceStub()
    try:
        response = client.get("/trends?period_type=week")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["period_type"] == "week"


def test_comparisons_accepts_rolling_window_parameter(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(id=1, strava_athlete_id=162181, display_name="Test Athlete", profile_picture_url=None)
    )
    app.dependency_overrides[DashboardReadService] = lambda: DashboardReadServiceStub()
    try:
        response = client.get("/comparisons?period_type=rolling_30d")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_comparisons_accepts_explicit_period_starts(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(id=1, strava_athlete_id=162181, display_name="Test Athlete", profile_picture_url=None)
    )
    app.dependency_overrides[DashboardReadService] = lambda: DashboardReadServiceStub()
    try:
        response = client.get("/comparisons?period_type=month&current_period_start=2026-03-01&previous_period_start=2026-02-01")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_activities_list_returns_rows(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(id=1, strava_athlete_id=162181, display_name="Test Athlete", profile_picture_url=None)
    )
    app.dependency_overrides[ActivityReadService] = lambda: ActivityReadServiceStub()
    try:
        response = client.get("/activities")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "Morning Run"


def test_activity_detail_returns_payload(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(id=1, strava_athlete_id=162181, display_name="Test Athlete", profile_picture_url=None)
    )
    app.dependency_overrides[ActivityReadService] = lambda: ActivityReadServiceStub()
    try:
        response = client.get("/activities/5")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["series"]["pace_display"][0] == "5:00"
    assert response.json()["series"]["altitude_meters"][0] == 200.0


def test_best_efforts_returns_items(client) -> None:
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(
        CurrentUserResponse(id=1, strava_athlete_id=162181, display_name="Test Athlete", profile_picture_url=None)
    )
    app.dependency_overrides[BestEffortReadService] = lambda: BestEffortReadServiceStub()
    try:
        response = client.get("/best-efforts")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["items"][0]["effort_code"] == "5km"


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


def test_cors_allows_frontend_origin(client) -> None:
    response = client.options(
        "/auth/session",
        headers={
            "origin": "http://localhost:5173",
            "access-control-request-method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"
