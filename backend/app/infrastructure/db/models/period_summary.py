from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class PeriodSummary(TimestampMixin, Base):
    __tablename__ = "period_summaries"
    __table_args__ = (
        Index(
            "ix_period_summaries_user_sport_period",
            "user_id",
            "sport_type",
            "period_type",
            "period_start",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    activity_count: Mapped[int] = mapped_column(default=0, nullable=False)
    total_distance_meters: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_moving_time_seconds: Mapped[int] = mapped_column(default=0, nullable=False)
    average_speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    average_pace_seconds_per_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_elevation_gain_meters: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    total_difficulty_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    user = relationship("User", back_populates="period_summaries")
