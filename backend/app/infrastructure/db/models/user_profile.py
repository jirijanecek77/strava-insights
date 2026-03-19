from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    aet_heart_rate_bpm: Mapped[int | None]
    ant_heart_rate_bpm: Mapped[int | None]
    aet_pace_min_per_km: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    ant_pace_min_per_km: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    user = relationship("User", back_populates="profile")
