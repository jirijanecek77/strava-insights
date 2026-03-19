from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class UserThresholdProfile(TimestampMixin, Base):
    __tablename__ = "user_threshold_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "effective_from", name="uq_user_threshold_profiles_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    aet_heart_rate_bpm: Mapped[int | None]
    ant_heart_rate_bpm: Mapped[int | None]
    aet_pace_min_per_km: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ant_pace_min_per_km: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    user = relationship("User", back_populates="threshold_profiles")
