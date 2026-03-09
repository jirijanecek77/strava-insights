from dataclasses import dataclass


@dataclass(slots=True)
class CreatedSyncJob:
    id: int
    user_id: int
    sync_type: str
    status: str
