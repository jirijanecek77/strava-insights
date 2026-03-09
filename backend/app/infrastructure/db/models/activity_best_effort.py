from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class ActivityBestEffort(TimestampMixin, Base):
    __tablename__ = "activity_best_efforts"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), nullable=False)
    effort_code: Mapped[str] = mapped_column(String(50), nullable=False)
    best_time_seconds: Mapped[int] = mapped_column(nullable=False)

    activity = relationship("Activity", back_populates="activity_best_efforts")
