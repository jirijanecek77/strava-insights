import logging
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import uuid4

from itsdangerous import BadSignature, URLSafeSerializer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.auth.dto import AuthenticatedUser, StravaAppCredentials
from app.application.auth.dto import StravaTokenPayload
from app.core.config import settings
from app.domain.schemas.auth import StravaCredentialStateResponse
from app.infrastructure.db.models.oauth_token import OauthToken
from app.infrastructure.db.models.strava_oauth_state import StravaOauthState
from app.infrastructure.db.models.user import User
from app.infrastructure.db.models.user_strava_app_credential import UserStravaAppCredential
from app.infrastructure.repositories.oauth_token_repository import OauthTokenRepository
from app.infrastructure.repositories.strava_oauth_state_repository import StravaOauthStateRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.repositories.user_strava_app_credential_repository import UserStravaAppCredentialRepository
from app.infrastructure.security.token_cipher import TokenCipher
from app.infrastructure.strava.client import StravaAuthClient


logger = logging.getLogger(__name__)


class StravaOAuthService:
    def __init__(
        self,
        db_session: Session = Depends(get_db_session),
        strava_client: StravaAuthClient = Depends(StravaAuthClient),
        token_cipher: TokenCipher = Depends(TokenCipher),
    ) -> None:
        self.db_session = db_session
        self.strava_client = strava_client
        self.token_cipher = token_cipher
        self.user_repository = UserRepository(db_session)
        self.oauth_token_repository = OauthTokenRepository(db_session)
        self.strava_app_credential_repository = UserStravaAppCredentialRepository(db_session)
        self.oauth_state_repository = StravaOauthStateRepository(db_session)

    def get_landing_credential_state(self, remembered_user_id: int | None) -> StravaCredentialStateResponse:
        if remembered_user_id is None:
            return self._empty_credential_state()

        user = self.user_repository.get_by_id(remembered_user_id)
        if user is None or not user.is_active:
            return self._empty_credential_state()

        credential = self.strava_app_credential_repository.get_for_user(remembered_user_id)
        if credential is None:
            return self._empty_credential_state()

        return StravaCredentialStateResponse(
            client_id=credential.client_id,
            has_saved_secret=True,
            can_connect=True,
            strava_api_settings_url=settings.strava_api_settings_url,
        )

    def start_login(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        use_saved_credentials: bool,
        remembered_user_id: int | None,
        request_client: str,
    ) -> str:
        credentials = self._resolve_start_login_credentials(
            client_id=client_id,
            client_secret=client_secret,
            use_saved_credentials=use_saved_credentials,
            remembered_user_id=remembered_user_id,
        )
        self.oauth_state_repository.delete_expired()
        raw_state = str(uuid4())
        signed_state = self._build_state_serializer().dumps({"state": raw_state, "client": request_client})
        pending_state = StravaOauthState(
            state_token=raw_state,
            client_id=credentials.client_id,
            client_secret_encrypted=self.token_cipher.encrypt(credentials.client_secret),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.strava_oauth_state_ttl_seconds),
        )
        self.oauth_state_repository.save(pending_state)
        self.db_session.commit()
        logger.info("Starting Strava OAuth login.", extra={"client.address": request_client})
        return self.build_authorization_url(credentials.client_id, signed_state)

    def build_authorization_url(self, client_id: str, state: str) -> str:
        query = urlencode(
            {
                "client_id": client_id,
                "redirect_uri": settings.strava_redirect_uri,
                "response_type": "code",
                "approval_prompt": "auto",
                "scope": settings.strava_scope,
                "state": state,
            }
        )
        return f"{settings.strava_authorize_url}?{query}"

    def authenticate_from_code(self, code: str, state: str) -> AuthenticatedUser:
        pending_state = self._consume_pending_state(state)
        credentials = StravaAppCredentials(
            client_id=pending_state.client_id,
            client_secret=self.token_cipher.decrypt(pending_state.client_secret_encrypted),
        )
        logger.info("Exchanging Strava authorization code for tokens.")
        token_payload = self.strava_client.exchange_code_for_token(code, credentials)
        user, is_new_user = self._upsert_user_with_token(token_payload)
        self._upsert_user_app_credentials(user.id, credentials)
        self.oauth_state_repository.delete(pending_state)
        self.db_session.commit()
        self.db_session.refresh(user)
        logger.info(
            "Authenticated Strava user.",
            extra={"user.id": user.id, "is_new_user": is_new_user, "strava_athlete_id": token_payload.athlete_id},
        )
        return AuthenticatedUser(
            id=user.id,
            strava_athlete_id=user.strava_athlete_id or token_payload.athlete_id,
            display_name=user.display_name,
            profile_picture_url=user.profile_picture_url,
            is_new_user=is_new_user,
        )

    def _resolve_start_login_credentials(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        use_saved_credentials: bool,
        remembered_user_id: int | None,
    ) -> StravaAppCredentials:
        if use_saved_credentials:
            if remembered_user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Saved Strava app credentials are not available.",
                )
            remembered_user = self.user_repository.get_by_id(remembered_user_id)
            if remembered_user is None or not remembered_user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This account has been disabled.",
                )
            stored_credential = self.strava_app_credential_repository.get_for_user(remembered_user_id)
            if stored_credential is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Saved Strava app credentials are not available.",
                )
            return StravaAppCredentials(
                client_id=stored_credential.client_id,
                client_secret=self.token_cipher.decrypt(stored_credential.client_secret_encrypted),
            )

        normalized_client_id = (client_id or "").strip()
        normalized_client_secret = (client_secret or "").strip()
        if not normalized_client_id or not normalized_client_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both Strava client ID and client secret are required.",
            )
        return StravaAppCredentials(client_id=normalized_client_id, client_secret=normalized_client_secret)

    def _consume_pending_state(self, signed_state: str) -> StravaOauthState:
        try:
            raw_payload = self._build_state_serializer().loads(signed_state)
        except BadSignature as exc:
            logger.error("Rejected Strava OAuth callback because state signature was invalid.")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.") from exc

        raw_state = raw_payload.get("state")
        if not raw_state:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")
        pending_state = self.oauth_state_repository.get_by_state_token(raw_state)
        if pending_state is None or pending_state.expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")
        return pending_state

    def _upsert_user_app_credentials(self, user_id: int, credentials: StravaAppCredentials) -> None:
        stored = self.strava_app_credential_repository.get_for_user(user_id)
        encrypted_secret = self.token_cipher.encrypt(credentials.client_secret)
        if stored is None:
            stored = UserStravaAppCredential(
                user_id=user_id,
                client_id=credentials.client_id,
                client_secret_encrypted=encrypted_secret,
            )
        else:
            stored.client_id = credentials.client_id
            stored.client_secret_encrypted = encrypted_secret
        self.strava_app_credential_repository.save(stored)

    def _upsert_user_with_token(self, token_payload: StravaTokenPayload) -> tuple[User, bool]:
        user = self.user_repository.get_by_strava_athlete_id(token_payload.athlete_id)
        is_new_user = user is None
        display_name = " ".join(
            part for part in [token_payload.athlete_firstname, token_payload.athlete_lastname] if part
        ) or f"Strava athlete {token_payload.athlete_id}"

        if user is None:
            logger.info("Creating new user from Strava token payload.", extra={"strava_athlete_id": token_payload.athlete_id})
            user = User(
                strava_athlete_id=token_payload.athlete_id,
                display_name=display_name,
                profile_picture_url=token_payload.athlete_profile,
            )
            self.user_repository.save(user)
        else:
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This account has been disabled.",
                )
            logger.info("Updating existing user from Strava token payload.", extra={"user.id": user.id})
            user.display_name = display_name
            user.profile_picture_url = token_payload.athlete_profile
        user.last_login_at = datetime.now(UTC)

        oauth_token = self.oauth_token_repository.get_by_user_and_provider(user.id)
        encrypted_access_token = self.token_cipher.encrypt(token_payload.access_token)
        encrypted_refresh_token = self.token_cipher.encrypt(token_payload.refresh_token)

        if oauth_token is None:
            logger.info("Creating OAuth token record.", extra={"user.id": user.id})
            oauth_token = OauthToken(
                user_id=user.id,
                provider="strava",
                access_token_encrypted=encrypted_access_token,
                refresh_token_encrypted=encrypted_refresh_token,
                expires_at=token_payload.expires_at.astimezone(UTC),
                scope=token_payload.scope,
                strava_athlete_id=token_payload.athlete_id,
            )
            self.oauth_token_repository.save(oauth_token)
        else:
            logger.info("Refreshing OAuth token record.", extra={"user.id": user.id})
            oauth_token.access_token_encrypted = encrypted_access_token
            oauth_token.refresh_token_encrypted = encrypted_refresh_token
            oauth_token.expires_at = token_payload.expires_at.astimezone(UTC)
            oauth_token.scope = token_payload.scope
            oauth_token.strava_athlete_id = token_payload.athlete_id
            self.oauth_token_repository.save(oauth_token)

        return user, is_new_user

    @staticmethod
    def _build_state_serializer() -> URLSafeSerializer:
        return URLSafeSerializer(settings.session_secret_key, salt="strava-oauth-state")

    @staticmethod
    def _empty_credential_state() -> StravaCredentialStateResponse:
        return StravaCredentialStateResponse(
            client_id=None,
            has_saved_secret=False,
            can_connect=False,
            strava_api_settings_url=settings.strava_api_settings_url,
        )
