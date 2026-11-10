from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class TrainingPlanRequest(Base):
    __tablename__ = "training_plan_requests"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "source_key", name="uq_training_plan_request_source"
        ),
        Index("ix_training_plan_requests_pending", "status", "next_attempt_at", "id"),
        Index("ix_training_plan_requests_user", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    sync_job_id: Mapped[int | None] = mapped_column(ForeignKey("sync_jobs.id"))
    source_key: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    target_start: Mapped[date | None]
    context_json: Mapped[dict | None] = mapped_column(JSON)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TrainingPlanDay(Base):
    __tablename__ = "training_plan_days"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "planned_date", name="uq_training_plan_day_user_date"
        ),
        CheckConstraint(
            "(kind = 'rest' AND distance_meters IS NULL AND pace_seconds_per_km IS NULL AND heart_rate_bpm IS NULL) OR (kind = 'run' AND distance_meters > 0 AND pace_seconds_per_km > 0 AND heart_rate_bpm > 0 AND distance_meters IS NOT NULL AND pace_seconds_per_km IS NOT NULL AND heart_rate_bpm IS NOT NULL)",
            name="ck_training_plan_day_targets",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("training_plan_requests.id"), nullable=False
    )
    planned_date: Mapped[date]
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    focus: Mapped[str] = mapped_column(String(20), nullable=False)
    distance_meters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    pace_seconds_per_km: Mapped[int | None]
    heart_rate_bpm: Mapped[int | None]
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
