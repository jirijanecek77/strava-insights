from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class StravaOauthState(TimestampMixin, Base):
    __tablename__ = "strava_oauth_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    state_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    client_secret_encrypted: Mapped[str] = mapped_column(String(4096), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
