from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class StravaAppCredentials:
    client_id: str
    client_secret: str


@dataclass(slots=True)
class StravaTokenPayload:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scope: str | None
    athlete_id: int
    athlete_firstname: str | None
    athlete_lastname: str | None
    athlete_profile: str | None


@dataclass(slots=True)
class AuthenticatedUser:
    id: int
    strava_athlete_id: int
    display_name: str
    profile_picture_url: str | None
    is_new_user: bool = False
