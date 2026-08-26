import logging
import re
from datetime import UTC, datetime

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.auth.dto import AuthenticatedUser, GarminCredentials
from app.domain.schemas.auth import GarminCredentialStateResponse
from app.infrastructure.db.models.garmin_credential import GarminCredential
from app.infrastructure.db.models.user import User
from app.infrastructure.garmin.client import (
    GarminAuthClient,
    GarminLoginError,
    GarminRateLimitError,
    GarminTemporaryError,
)
from app.infrastructure.repositories.garmin_credential_repository import GarminCredentialRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.security.token_cipher import TokenCipher

logger = logging.getLogger(__name__)
def _safe_failure_details(exc: BaseException) -> str:
    details: list[str] = []
    current: BaseException | None = exc
    while current is not None and len(details) < 4:
        message = str(current)
        message = re.sub(r"\{.*\}", "<REDACTED_PAYLOAD>", message)
        message = re.sub(r"https?://[^\s)]+", "<REDACTED_URL>", message)
        message = re.sub(r"[\w.+-]+@[\w.-]+", "<REDACTED_EMAIL>", message)
        message = re.sub(
            r"\b(password|token|cookie|authorization|bearer|refresh[-_ ]?token)\s*[:=]\s*[^,; ]+",
            r"\1=<REDACTED>",
            message,
            flags=re.I,
        )
        details.append(f"{type(current).__name__}: {message[:160]}")
        current = current.__cause__ or current.__context__
    return " <- ".join(details)


def _garmin_failure_response(exc: GarminLoginError, default_detail: str) -> HTTPException:
    if isinstance(exc, GarminRateLimitError):
        return HTTPException(status_code=429, detail="Garmin login is temporarily rate limited. Try again later.")
    if isinstance(exc, GarminTemporaryError):
        return HTTPException(status_code=503, detail="Garmin is temporarily unavailable. Try again later.")
    return HTTPException(status_code=401, detail=default_detail)


class GarminCredentialService:
    def __init__(self, db_session: Session = Depends(get_db_session), garmin_client: GarminAuthClient = Depends(GarminAuthClient), token_cipher: TokenCipher = Depends(TokenCipher)) -> None:
        self.db_session, self.garmin_client, self.token_cipher = db_session, garmin_client, token_cipher
        self.users, self.credentials = UserRepository(db_session), GarminCredentialRepository(db_session)

    def state(self, remembered_user_id: int | None) -> GarminCredentialStateResponse:
        credential = self.credentials.get_for_user(remembered_user_id) if remembered_user_id else None
        return GarminCredentialStateResponse(external_user_id=credential.external_user_id if credential else None, has_saved_secret=credential is not None, can_connect=credential is not None)

    def authenticate(self, credentials: GarminCredentials, remembered_user_id: int | None) -> AuthenticatedUser:
        try:
            client, profile = self.garmin_client.login(credentials.email, credentials.password or "")
        except GarminLoginError as exc:
            logger.warning("Garmin login failure: %s", _safe_failure_details(exc))
            raise _garmin_failure_response(exc, "Garmin login failed. Check the email and password.") from exc
        return self._persist(client, profile, credentials.email, remembered_user_id)

    def authenticate_saved(self, user_id: int) -> AuthenticatedUser:
        stored = self.credentials.get_for_user(user_id)
        if stored is None:
            raise HTTPException(status_code=400, detail="Saved Garmin credentials are not available.")
        try:
            client, profile = self.garmin_client.reconnect(self.token_cipher.decrypt(stored.token_json_encrypted))
        except GarminLoginError as exc:
            logger.warning("Garmin saved-session failure: %s", _safe_failure_details(exc))
            raise _garmin_failure_response(exc, "Saved Garmin session expired. Sign in again.") from exc
        return self._persist(client, profile, self.token_cipher.decrypt(stored.email_encrypted), user_id)

    def _persist(self, client, profile, email: str, remembered_user_id: int | None) -> AuthenticatedUser:
        user = self.users.get_by_id(remembered_user_id) if remembered_user_id else self.users.get_by_external_user_id(profile.external_user_id)
        if user is not None and not user.is_active:
            raise HTTPException(status_code=403, detail="This account has been disabled.")
        is_new = user is None
        user = user or User(external_user_id=profile.external_user_id, source_provider="garmin", display_name=profile.display_name)
        user.external_user_id, user.source_provider, user.display_name = profile.external_user_id, "garmin", profile.display_name
        user.profile_picture_url, user.last_login_at = profile.profile_picture_url, datetime.now(UTC)
        self.users.save(user)
        stored = self.credentials.get_for_user(user.id)
        if stored is None:
            stored = GarminCredential(user_id=user.id, email_encrypted="", token_json_encrypted="", external_user_id=profile.external_user_id)
        stored.email_encrypted = self.token_cipher.encrypt(email)
        stored.token_json_encrypted = self.token_cipher.encrypt(self.garmin_client.token_json(client))
        stored.external_user_id = profile.external_user_id
        self.credentials.save(stored)
        self.db_session.commit()
        return AuthenticatedUser(user.id, profile.external_user_id, user.display_name, user.profile_picture_url, is_new)
