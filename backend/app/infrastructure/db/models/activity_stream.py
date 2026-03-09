from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin


class ActivityStream(TimestampMixin, Base):
    __tablename__ = "activity_streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id"), unique=True, nullable=False)
    time_stream: Mapped[dict | None] = mapped_column(JSONB)
    distance_stream: Mapped[dict | None] = mapped_column(JSONB)
    latlng_stream: Mapped[dict | None] = mapped_column(JSONB)
    altitude_stream: Mapped[dict | None] = mapped_column(JSONB)
    velocity_smooth_stream: Mapped[dict | None] = mapped_column(JSONB)
    heartrate_stream: Mapped[dict | None] = mapped_column(JSONB)
    derived_series: Mapped[dict | None] = mapped_column(JSONB)
    interval_analysis: Mapped[dict | None] = mapped_column(JSONB)

    activity = relationship("Activity", back_populates="stream")
