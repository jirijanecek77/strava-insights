from sqlalchemy.orm import Session

from app.infrastructure.db.models.intervals_credential import IntervalsCredential


class IntervalsCredentialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_user(self, user_id: int) -> IntervalsCredential | None:
        return (
            self.session.query(IntervalsCredential)
            .filter(IntervalsCredential.user_id == user_id)
            .one_or_none()
        )

    def save(self, credential: IntervalsCredential) -> IntervalsCredential:
        self.session.add(credential)
        self.session.flush()
        return credential
