from pydantic import BaseModel, ConfigDict


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strava_athlete_id: int | None = None
    display_name: str
    profile_picture_url: str | None = None
