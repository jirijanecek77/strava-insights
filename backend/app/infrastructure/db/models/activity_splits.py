from sqlalchemy import ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ActivitySplits(Base):
    __tablename__ = "activity_splits"

    activity_id: Mapped[int] = mapped_column(ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="unavailable", server_default="unavailable")
    laps: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
