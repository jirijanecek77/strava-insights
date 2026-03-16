from datetime import UTC, datetime

from app.application.auth.dto import StravaTokenPayload
from app.application.auth.oauth import StravaOAuthService
from app.infrastructure.security.token_cipher import TokenCipher


class StravaClientStub:
    def exchange_code_for_token(self, code: str) -> StravaTokenPayload:
        assert code == "valid-code"
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
    def __init__(self, value):
        self._value = value

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        return self._value


class SessionStub:
    def __init__(self) -> None:
        self.user = None
        self.oauth = None
        self.added = []

    def query(self, model):
        if model.__name__ == "User":
            return QueryStub(self.user)
        return QueryStub(self.oauth)

    def add(self, value):
        self.added.append(value)
        if value.__class__.__name__ == "User":
            value.id = 1
            self.user = value
        else:
            self.oauth = value

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, _value):
        return None


def test_build_authorization_url_contains_required_parameters() -> None:
    service = StravaOAuthService(
        db_session=SessionStub(),
        strava_client=StravaClientStub(),
        token_cipher=TokenCipher(),
    )

    url = service.build_authorization_url("signed-state")

    assert "client_id=" in url
    assert "redirect_uri=" in url
    assert "state=signed-state" in url


def test_authenticate_from_code_persists_user_and_encrypted_tokens() -> None:
    session = SessionStub()
    service = StravaOAuthService(
        db_session=session,
        strava_client=StravaClientStub(),
        token_cipher=TokenCipher(),
    )

    authenticated_user = service.authenticate_from_code("valid-code")

    assert authenticated_user.id == 1
    assert authenticated_user.strava_athlete_id == 162181
    assert session.user is not None
    assert session.oauth is not None
    assert session.oauth.access_token_encrypted != "access-token"
    assert session.oauth.refresh_token_encrypted != "refresh-token"
