from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class BestEffort(TimestampMixin, Base):
    __tablename__ = "best_efforts"
    __table_args__ = (
        Index("ix_best_efforts_user_sport_effort_code", "user_id", "sport_type", "effort_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(50), nullable=False)
    effort_code: Mapped[str] = mapped_column(String(50), nullable=False)
    best_time_seconds: Mapped[int] = mapped_column(nullable=False)
    distance_meters: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    activity_id: Mapped[int | None] = mapped_column(ForeignKey("activities.id"))
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user = relationship("User", back_populates="best_efforts")
