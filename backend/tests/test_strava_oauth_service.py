from datetime import UTC, datetime, timedelta

from app.application.auth.dto import StravaAppCredentials, StravaTokenPayload
from app.application.auth.oauth import StravaOAuthService
from app.infrastructure.security.token_cipher import TokenCipher


class StravaClientStub:
    def __init__(self) -> None:
        self.last_exchange = None

    def exchange_code_for_token(self, code: str, credentials: StravaAppCredentials) -> StravaTokenPayload:
        assert code == "valid-code"
        self.last_exchange = credentials
        return StravaTokenPayload(
            access_token="access-token",
            refresh_token="refresh-token",
            expires_at=datetime(2026, 3, 9, 12, 0, tzinfo=UTC),
            scope="read,activity:read_all",
            athlete_id=162181,
            athlete_firstname="Jiri",
            athlete_lastname="Janecek",
            athlete_profile="https://example.com/profile.png",
        )


class QueryStub:
    def __init__(self, model_name: str, session: "SessionStub"):
        self.model_name = model_name
        self.session = session

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        if self.model_name == "User":
            return self.session.user
        if self.model_name == "OauthToken":
            return self.session.oauth
        if self.model_name == "UserStravaAppCredential":
            return self.session.app_credential
        if self.model_name == "StravaOauthState":
            return self.session.oauth_state
        return None

    def delete(self):
        if self.model_name == "StravaOauthState":
            self.session.oauth_state = None
        return 1


class SessionStub:
    def __init__(self) -> None:
        self.user = None
        self.oauth = None
        self.app_credential = None
        self.oauth_state = None
        self.added = []

    def query(self, model):
        return QueryStub(model.__name__, self)

    def add(self, value):
        self.added.append(value)
        if value.__class__.__name__ == "User":
            value.id = 1
            self.user = value
        elif value.__class__.__name__ == "OauthToken":
            self.oauth = value
        elif value.__class__.__name__ == "UserStravaAppCredential":
            self.app_credential = value
        elif value.__class__.__name__ == "StravaOauthState":
            self.oauth_state = value

    def delete(self, value):
        if value is self.oauth_state:
            self.oauth_state = None

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, _value):
        return None


def _build_service(*, session: SessionStub | None = None, strava_client: StravaClientStub | None = None) -> StravaOAuthService:
    return StravaOAuthService(
        db_session=session or SessionStub(),
        strava_client=strava_client or StravaClientStub(),
        token_cipher=TokenCipher(),
    )


def test_build_authorization_url_contains_required_parameters() -> None:
    service = _build_service()

    url = service.build_authorization_url("12345", "signed-state")

    assert "client_id=12345" in url
    assert "redirect_uri=" in url
    assert "state=signed-state" in url


def test_start_login_persists_pending_state_and_uses_manual_credentials() -> None:
    session = SessionStub()
    service = _build_service(session=session)

    url = service.start_login(
        client_id="12345",
        client_secret="manual-secret",
        use_saved_credentials=False,
        remembered_user_id=None,
        request_client="127.0.0.1",
    )

    assert "client_id=12345" in url
    assert "state=" in url
    assert session.oauth_state is not None
    assert session.oauth_state.client_id == "12345"
    assert session.oauth_state.client_secret_encrypted != "manual-secret"


def test_authenticate_from_code_persists_user_tokens_and_app_credentials() -> None:
    session = SessionStub()
    strava_client = StravaClientStub()
    service = _build_service(session=session, strava_client=strava_client)
    state_url = service.start_login(
        client_id="12345",
        client_secret="manual-secret",
        use_saved_credentials=False,
        remembered_user_id=None,
        request_client="127.0.0.1",
    )
    state = state_url.split("state=")[1]

    authenticated_user = service.authenticate_from_code("valid-code", state)

    assert authenticated_user.id == 1
    assert authenticated_user.strava_athlete_id == 162181
    assert strava_client.last_exchange == StravaAppCredentials(client_id="12345", client_secret="manual-secret")
    assert session.user is not None
    assert session.oauth is not None
    assert session.app_credential is not None
    assert session.oauth.access_token_encrypted != "access-token"
    assert session.oauth.refresh_token_encrypted != "refresh-token"
    assert session.app_credential.client_id == "12345"
    assert session.app_credential.client_secret_encrypted != "manual-secret"
    assert session.oauth_state is None


def test_landing_credential_state_returns_saved_credential_summary() -> None:
    session = SessionStub()
    cipher = TokenCipher()
    session.app_credential = type(
        "SavedCredential",
        (),
        {
            "user_id": 1,
            "client_id": "98765",
            "client_secret_encrypted": cipher.encrypt("stored-secret"),
        },
    )()
    service = _build_service(session=session)

    payload = service.get_landing_credential_state(1)

    assert payload.client_id == "98765"
    assert payload.has_saved_secret is True
    assert payload.can_connect is True


def test_start_login_uses_saved_credentials_for_remembered_user() -> None:
    session = SessionStub()
    cipher = TokenCipher()
    session.app_credential = type(
        "SavedCredential",
        (),
        {
            "user_id": 1,
            "client_id": "24680",
            "client_secret_encrypted": cipher.encrypt("stored-secret"),
        },
    )()
    service = _build_service(session=session)

    url = service.start_login(
        client_id=None,
        client_secret=None,
        use_saved_credentials=True,
        remembered_user_id=1,
        request_client="127.0.0.1",
    )

    assert "client_id=24680" in url
    assert session.oauth_state is not None
