from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminUserAuditItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    strava_athlete_id: int | None = None
    email: str | None = None
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserAuditItem]
