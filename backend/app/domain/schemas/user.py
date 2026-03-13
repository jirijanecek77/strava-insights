from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strava_athlete_id: int | None = None
    display_name: str
    profile_picture_url: str | None = None


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    birthday: date | None = None
    speed_max: Decimal | None = None
    max_heart_rate_override: int | None = None


class UpdateUserProfileRequest(BaseModel):
    birthday: date | None = None
    speed_max: Decimal | None = None
    max_heart_rate_override: int | None = None
