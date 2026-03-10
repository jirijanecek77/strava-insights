from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class Activity(TimestampMixin, Base):
    __tablename__ = "activities"
    __table_args__ = (
        Index("ix_activities_user_start_date_desc", "user_id", "start_date_utc"),
        Index("ix_activities_user_sport_start_date_desc", "user_id", "sport_type", "start_date_utc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    strava_activity_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    start_date_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    distance_meters: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    moving_time_seconds: Mapped[int] = mapped_column(nullable=False)
    moving_time_display: Mapped[str | None] = mapped_column(String(32))
    elapsed_time_seconds: Mapped[int | None]
    total_elevation_gain_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    elev_high_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    elev_low_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    average_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    average_speed_kph: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    max_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    average_heartrate_bpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    max_heartrate_bpm: Mapped[int | None]
    average_cadence: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    average_pace_seconds_per_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    average_pace_display: Mapped[str | None] = mapped_column(String(16))
    summary_metric_display: Mapped[str | None] = mapped_column(String(32))
    difficulty_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    start_latlng: Mapped[dict | None] = mapped_column(JSONB)

    user = relationship("User", back_populates="activities")
    stream = relationship("ActivityStream", back_populates="activity", uselist=False)
    activity_best_efforts = relationship("ActivityBestEffort", back_populates="activity")
