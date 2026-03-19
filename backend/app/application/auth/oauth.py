import logging
from datetime import UTC
from urllib.parse import urlencode

from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.auth.dto import AuthenticatedUser, StravaTokenPayload
from app.core.config import settings
from app.infrastructure.db.models.oauth_token import OauthToken
from app.infrastructure.db.models.user import User
from app.infrastructure.repositories.oauth_token_repository import OauthTokenRepository
from app.infrastructure.repositories.user_repository import UserRepository
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

    def build_authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": settings.strava_client_id,
                "redirect_uri": settings.strava_redirect_uri,
                "response_type": "code",
                "approval_prompt": "auto",
                "scope": settings.strava_scope,
                "state": state,
            }
        )
        return f"{settings.strava_authorize_url}?{query}"

    def authenticate_from_code(self, code: str) -> AuthenticatedUser:
        logger.info("Exchanging Strava authorization code for tokens.")
        token_payload = self.strava_client.exchange_code_for_token(code)
        user, is_new_user = self._upsert_user_with_token(token_payload)
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
            logger.info("Updating existing user from Strava token payload.", extra={"user.id": user.id})
            user.display_name = display_name
            user.profile_picture_url = token_payload.athlete_profile

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
