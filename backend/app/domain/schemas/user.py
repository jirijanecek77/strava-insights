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

    aet_heart_rate_bpm: int | None = None
    ant_heart_rate_bpm: int | None = None
    aet_pace_min_per_km: Decimal | None = None
    ant_pace_min_per_km: Decimal | None = None


class UpdateUserProfileRequest(BaseModel):
    aet_heart_rate_bpm: int | None = None
    ant_heart_rate_bpm: int | None = None
    aet_pace_min_per_km: Decimal | None = None
    ant_pace_min_per_km: Decimal | None = None
