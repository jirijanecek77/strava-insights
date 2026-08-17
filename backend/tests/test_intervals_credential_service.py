from fastapi import HTTPException

from app.application.auth.credentials import IntervalsCredentialService
from app.application.auth.dto import IntervalsCredentials
from app.infrastructure.intervals.client import (
    IntervalsAthleteProfile,
    format_intervals_athlete_id,
)
from app.infrastructure.security.token_cipher import TokenCipher


class IntervalsClientStub:
    def __init__(self) -> None:
        self.last_credentials = None

    def get_athlete_profile(
        self, *, athlete_id: str, api_key: str
    ) -> IntervalsAthleteProfile:
        self.last_credentials = IntervalsCredentials(
            athlete_id=athlete_id, api_key=api_key
        )
        return IntervalsAthleteProfile(
            athlete_id=162181,
            display_name="Jiri Janecek",
            profile_picture_url="https://example.com/profile.png",
        )


def test_format_intervals_athlete_id_preserves_required_i_prefix() -> None:
    assert format_intervals_athlete_id("632291") == "i632291"
    assert format_intervals_athlete_id("i632291") == "i632291"


class QueryStub:
    def __init__(self, model_name: str, session: "SessionStub"):
        self.model_name = model_name
        self.session = session

    def filter(self, *args, **kwargs):
        return self

    def one_or_none(self):
        if self.model_name == "User":
            return self.session.user
        if self.model_name == "IntervalsCredential":
            return self.session.credential
        return None


class SessionStub:
    def __init__(self) -> None:
        self.user = None
        self.credential = None
        self.added = []

    def query(self, model):
        return QueryStub(model.__name__, self)

    def add(self, value):
        self.added.append(value)
        if value.__class__.__name__ == "User":
            value.id = 1
            self.user = value
        elif value.__class__.__name__ == "IntervalsCredential":
            self.credential = value

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, _value):
        return None


def _build_service(
    *,
    session: SessionStub | None = None,
    intervals_client: IntervalsClientStub | None = None,
) -> IntervalsCredentialService:
    return IntervalsCredentialService(
        db_session=session or SessionStub(),
        intervals_client=intervals_client or IntervalsClientStub(),
        token_cipher=TokenCipher(),
    )


def test_authenticate_with_manual_credentials_persists_user_and_credentials() -> None:
    session = SessionStub()
    intervals_client = IntervalsClientStub()
    service = _build_service(session=session, intervals_client=intervals_client)

    authenticated_user = service.authenticate_with_credentials(
        athlete_id="162181",
        api_key="manual-key",
        use_saved_credentials=False,
        remembered_user_id=None,
    )

    assert authenticated_user.id == 1
    assert authenticated_user.strava_athlete_id == 162181
    assert intervals_client.last_credentials == IntervalsCredentials(
        athlete_id="162181", api_key="manual-key"
    )
    assert session.user is not None
    assert session.credential is not None
    assert session.credential.athlete_id == "162181"
    assert session.credential.api_key_encrypted != "manual-key"
    assert session.user.last_login_at is not None


def test_landing_credential_state_returns_saved_credential_summary() -> None:
    session = SessionStub()
    session.user = type("SavedUser", (), {"id": 1, "is_active": True})()
    cipher = TokenCipher()
    session.credential = type(
        "SavedCredential",
        (),
        {
            "user_id": 1,
            "athlete_id": "98765",
            "api_key_encrypted": cipher.encrypt("stored-key"),
        },
    )()
    service = _build_service(session=session)

    payload = service.get_landing_credential_state(1)

    assert payload.athlete_id == "98765"
    assert payload.has_saved_secret is True
    assert payload.can_connect is True


def test_authenticate_uses_saved_credentials_for_remembered_user() -> None:
    session = SessionStub()
    session.user = type(
        "SavedUser",
        (),
        {
            "id": 1,
            "is_active": True,
            "strava_athlete_id": 162181,
            "display_name": "Saved Athlete",
            "profile_picture_url": None,
            "last_login_at": None,
        },
    )()
    cipher = TokenCipher()
    session.credential = type(
        "SavedCredential",
        (),
        {
            "user_id": 1,
            "athlete_id": "24680",
            "api_key_encrypted": cipher.encrypt("stored-key"),
        },
    )()
    intervals_client = IntervalsClientStub()
    service = _build_service(session=session, intervals_client=intervals_client)

    authenticated_user = service.authenticate_with_credentials(
        athlete_id=None,
        api_key=None,
        use_saved_credentials=True,
        remembered_user_id=1,
    )

    assert authenticated_user.id == 1
    assert intervals_client.last_credentials == IntervalsCredentials(
        athlete_id="24680", api_key="stored-key"
    )


def test_authenticate_rejects_disabled_remembered_user() -> None:
    session = SessionStub()
    session.user = type("DisabledUser", (), {"id": 1, "is_active": False})()
    service = _build_service(session=session)

    try:
        service.authenticate_with_credentials(
            athlete_id=None,
            api_key=None,
            use_saved_credentials=True,
            remembered_user_id=1,
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "This account has been disabled."
    else:
        raise AssertionError("Expected disabled remembered user to be rejected.")
