from sqlalchemy.orm import Session

from app.infrastructure.db.models.garmin_credential import GarminCredential


class GarminCredentialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> GarminCredential | None:
        return (
            self.session.query(GarminCredential)
            .filter(GarminCredential.user_id == user_id)
            .one_or_none()
        )

    def save(self, credential: GarminCredential) -> GarminCredential:
        self.session.add(credential)
        self.session.flush()
        return credential
