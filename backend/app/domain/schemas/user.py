from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strava_athlete_id: int | None = None
    display_name: str
    profile_picture_url: str | None = None


class UserThresholdProfileItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    effective_from: date
    aet_heart_rate_bpm: int | None = None
    ant_heart_rate_bpm: int | None = None
    aet_pace_min_per_km: Decimal | None = None
    ant_pace_min_per_km: Decimal | None = None


class UserProfileResponse(BaseModel):
    items: list[UserThresholdProfileItem]
    current: UserThresholdProfileItem | None = None


class UpdateUserProfileRequest(BaseModel):
    effective_from: date
    aet_heart_rate_bpm: int | None = None
    ant_heart_rate_bpm: int | None = None
    aet_pace_min_per_km: Decimal | None = None
    ant_pace_min_per_km: Decimal | None = None
