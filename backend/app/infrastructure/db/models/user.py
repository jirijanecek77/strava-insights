from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    strava_athlete_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_picture_url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    oauth_tokens = relationship("OauthToken", back_populates="user")
    activities = relationship("Activity", back_populates="user")
    period_summaries = relationship("PeriodSummary", back_populates="user")
    best_efforts = relationship("BestEffort", back_populates="user")
    sync_jobs = relationship("SyncJob", back_populates="user")
    sync_checkpoints = relationship("SyncCheckpoint", back_populates="user")
    threshold_profiles = relationship("UserThresholdProfile", back_populates="user")
    strava_app_credential = relationship("UserStravaAppCredential", back_populates="user", uselist=False)
