"""Append-only provider accounting; no prompts, output text or credentials."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ProviderAttempt(Base):
    __tablename__ = "ai_provider_attempts"
    __table_args__ = (
        UniqueConstraint(
            "operation", "work_id", "lease_token", name="uq_ai_attempt_claim"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operation: Mapped[str] = mapped_column(String(20))
    work_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(Integer)
    lease_token: Mapped[str] = mapped_column(String(36))
    input_revision: Mapped[str] = mapped_column(String(64))
    prompt_fingerprint: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(32), default="unknown")
    usage: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
