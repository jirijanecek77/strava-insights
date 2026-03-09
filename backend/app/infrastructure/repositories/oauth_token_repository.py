from sqlalchemy.orm import Session

from app.infrastructure.db.models.oauth_token import OauthToken


class OauthTokenRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_user_and_provider(self, user_id: int, provider: str = "strava") -> OauthToken | None:
        return (
            self.session.query(OauthToken)
            .filter(OauthToken.user_id == user_id, OauthToken.provider == provider)
            .one_or_none()
        )

    def save(self, oauth_token: OauthToken) -> OauthToken:
        self.session.add(oauth_token)
        self.session.flush()
        return oauth_token
