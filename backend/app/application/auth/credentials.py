import logging
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.application.auth.dto import AuthenticatedUser, IntervalsCredentials
from app.core.config import settings
from app.domain.schemas.auth import IntervalsCredentialStateResponse
from app.infrastructure.db.models.intervals_credential import IntervalsCredential
from app.infrastructure.db.models.user import User
from app.infrastructure.intervals.client import IntervalsAuthClient, IntervalsAthleteProfile
from app.infrastructure.repositories.intervals_credential_repository import IntervalsCredentialRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.infrastructure.security.token_cipher import TokenCipher


logger = logging.getLogger(__name__)


class IntervalsCredentialService:
    def __init__(
        self,
        db_session: Session = Depends(get_db_session),
        intervals_client: IntervalsAuthClient = Depends(IntervalsAuthClient),
        token_cipher: TokenCipher = Depends(TokenCipher),
    ) -> None:
        self.db_session = db_session
        self.intervals_client = intervals_client
        self.token_cipher = token_cipher
        self.user_repository = UserRepository(db_session)
        self.credential_repository = IntervalsCredentialRepository(db_session)

    def get_landing_credential_state(self, remembered_user_id: int | None) -> IntervalsCredentialStateResponse:
        if remembered_user_id is None:
            return self._empty_credential_state()

        user = self.user_repository.get_by_id(remembered_user_id)
        if user is None or not user.is_active:
            return self._empty_credential_state()

        credential = self.credential_repository.get_for_user(remembered_user_id)
        if credential is None:
            return self._empty_credential_state()

        return IntervalsCredentialStateResponse(
            athlete_id=credential.athlete_id,
            has_saved_secret=True,
            can_connect=True,
            intervals_settings_url=settings.intervals_settings_url,
        )

    def authenticate_with_credentials(
        self,
        *,
        athlete_id: str | None,
        api_key: str | None,
        use_saved_credentials: bool,
        remembered_user_id: int | None,
    ) -> AuthenticatedUser:
        credentials = self._resolve_credentials(
            athlete_id=athlete_id,
            api_key=api_key,
            use_saved_credentials=use_saved_credentials,
            remembered_user_id=remembered_user_id,
        )
        logger.info("Validating Intervals.icu credentials.")
        try:
            profile = self.intervals_client.get_athlete_profile(
                athlete_id=credentials.athlete_id,
                api_key=credentials.api_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            logger.warning("Intervals.icu credential validation failed.", exc_info=(type(exc), exc, exc.__traceback__))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Intervals.icu credentials could not be validated.",
            ) from exc

        user, is_new_user = self._upsert_user_with_credentials(
            profile=profile,
            credentials=credentials,
            preferred_user_id=remembered_user_id,
        )
        self.db_session.commit()
        self.db_session.refresh(user)
        logger.info(
            "Authenticated Intervals.icu user.",
            extra={"user.id": user.id, "is_new_user": is_new_user, "intervals_athlete_id": profile.athlete_id},
        )
        return AuthenticatedUser(
            id=user.id,
            strava_athlete_id=user.strava_athlete_id or profile.athlete_id,
            display_name=user.display_name,
            profile_picture_url=user.profile_picture_url,
            is_new_user=is_new_user,
        )

    def _resolve_credentials(
        self,
        *,
        athlete_id: str | None,
        api_key: str | None,
        use_saved_credentials: bool,
        remembered_user_id: int | None,
    ) -> IntervalsCredentials:
        if use_saved_credentials:
            if remembered_user_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Saved Intervals.icu credentials are not available.")
            remembered_user = self.user_repository.get_by_id(remembered_user_id)
            if remembered_user is None or not remembered_user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled.")
            stored_credential = self.credential_repository.get_for_user(remembered_user_id)
            if stored_credential is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Saved Intervals.icu credentials are not available.")
            return IntervalsCredentials(
                athlete_id=stored_credential.athlete_id,
                api_key=self.token_cipher.decrypt(stored_credential.api_key_encrypted),
            )

        normalized_athlete_id = (athlete_id or "").strip()
        normalized_api_key = (api_key or "").strip()
        if not normalized_athlete_id or not normalized_api_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both Intervals.icu athlete ID and API key are required.")
        return IntervalsCredentials(athlete_id=normalized_athlete_id, api_key=normalized_api_key)

    def _upsert_user_with_credentials(
        self,
        *,
        profile: IntervalsAthleteProfile,
        credentials: IntervalsCredentials,
        preferred_user_id: int | None,
    ) -> tuple[User, bool]:
        user = self._resolve_user_for_login(profile, preferred_user_id)
        is_new_user = user.id is None

        user.strava_athlete_id = profile.athlete_id
        user.display_name = profile.display_name
        user.profile_picture_url = profile.profile_picture_url
        user.last_login_at = datetime.now(UTC)
        if user.id is None:
            self.user_repository.save(user)
        else:
            self.user_repository.save(user)

        self._upsert_credentials(user.id, credentials)
        return user, is_new_user

    def _resolve_user_for_login(self, profile: IntervalsAthleteProfile, preferred_user_id: int | None) -> User:
        if preferred_user_id is not None:
            remembered_user = self.user_repository.get_by_id(preferred_user_id)
            if remembered_user is not None:
                if not remembered_user.is_active:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled.")
                return remembered_user

        existing_user = self.user_repository.get_by_strava_athlete_id(profile.athlete_id)
        if existing_user is not None:
            if not existing_user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been disabled.")
            return existing_user

        return User(
            strava_athlete_id=profile.athlete_id,
            display_name=profile.display_name,
            profile_picture_url=profile.profile_picture_url,
        )

    def _upsert_credentials(self, user_id: int, credentials: IntervalsCredentials) -> None:
        stored = self.credential_repository.get_for_user(user_id)
        encrypted_api_key = self.token_cipher.encrypt(credentials.api_key)
        if stored is None:
            stored = IntervalsCredential(
                user_id=user_id,
                athlete_id=credentials.athlete_id,
                api_key_encrypted=encrypted_api_key,
            )
        else:
            stored.athlete_id = credentials.athlete_id
            stored.api_key_encrypted = encrypted_api_key
        self.credential_repository.save(stored)

    @staticmethod
    def _empty_credential_state() -> IntervalsCredentialStateResponse:
        return IntervalsCredentialStateResponse(
            athlete_id=None,
            has_saved_secret=False,
            can_connect=False,
            intervals_settings_url=settings.intervals_settings_url,
        )
