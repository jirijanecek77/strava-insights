from sqlalchemy.orm import Session

from app.infrastructure.db.models.user_strava_app_credential import UserStravaAppCredential


class UserStravaAppCredentialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> UserStravaAppCredential | None:
        return (
            self.session.query(UserStravaAppCredential)
            .filter(UserStravaAppCredential.user_id == user_id)
            .one_or_none()
        )

    def save(self, credential: UserStravaAppCredential) -> UserStravaAppCredential:
        self.session.add(credential)
        self.session.flush()
        return credential
