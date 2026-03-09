from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    birthday: Mapped[date | None] = mapped_column(Date)
    speed_max: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    max_heart_rate_override: Mapped[int | None]

    user = relationship("User", back_populates="profile")
