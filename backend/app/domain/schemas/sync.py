from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SyncStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    sync_type: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress_total: int | None = None
    progress_completed: int | None = None
    error_message: str | None = None
