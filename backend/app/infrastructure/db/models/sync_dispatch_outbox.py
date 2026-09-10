from app.infrastructure.db.base import Base
from app.infrastructure.db.models.mixins import TimestampMixin
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class SyncDispatchOutbox(TimestampMixin, Base):
    """A durable command to publish one accepted sync job to Celery."""

    __tablename__ = "sync_dispatch_outbox"
    __table_args__ = (
        Index(
            "ix_sync_dispatch_outbox_pending",
            "status",
            "next_attempt_at",
            "created_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_job_id: Mapped[int] = mapped_column(
        ForeignKey("sync_jobs.id"), unique=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
