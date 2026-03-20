from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.infrastructure.db.models.strava_oauth_state import StravaOauthState


class StravaOauthStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_state_token(self, state_token: str) -> StravaOauthState | None:
        return (
            self.session.query(StravaOauthState)
            .filter(StravaOauthState.state_token == state_token)
            .one_or_none()
        )

    def save(self, state: StravaOauthState) -> StravaOauthState:
        self.session.add(state)
        self.session.flush()
        return state

    def delete(self, state: StravaOauthState) -> None:
        self.session.delete(state)
        self.session.flush()

    def delete_expired(self) -> None:
        self.session.query(StravaOauthState).filter(StravaOauthState.expires_at <= datetime.now(UTC)).delete()
        self.session.flush()
