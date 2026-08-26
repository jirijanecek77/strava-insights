from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_user_id: Mapped[str | None] = mapped_column(String(255))
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="garmin")
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_picture_url: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    activities = relationship("Activity", back_populates="user")
    period_summaries = relationship("PeriodSummary", back_populates="user")
    best_efforts = relationship("BestEffort", back_populates="user")
    sync_jobs = relationship("SyncJob", back_populates="user")
    sync_checkpoints = relationship("SyncCheckpoint", back_populates="user")
    threshold_profiles = relationship("UserThresholdProfile", back_populates="user")
    garmin_credential = relationship("GarminCredential", back_populates="user", uselist=False)
