from dataclasses import dataclass


@dataclass(slots=True)
class IntervalsCredentials:
    athlete_id: str
    api_key: str


@dataclass(slots=True)
class AuthenticatedUser:
    id: int
    strava_athlete_id: int
    display_name: str
    profile_picture_url: str | None
    is_new_user: bool = False
