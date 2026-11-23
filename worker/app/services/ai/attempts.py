"""Durable accounting begins immediately before each HTTP attempt."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint, func, update
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.services.ai.contracts import InputSnapshot, ProviderUsage


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


class DatabaseAttemptRecorder:
    def __init__(self, session, owns):
        self.session = session
        self.owns = owns

    def begin(
        self,
        snapshot: InputSnapshot,
        *,
        model: str,
        metadata: ProviderUsage | None = None
    ) -> str:
        from app.services.ai.contracts import ObsoleteWork

        if not self.owns(snapshot.claim):
            raise ObsoleteWork("Provider attempt belongs to an obsolete claim")
        identity = str(uuid4())
        self.session.add(
            ProviderAttempt(
                id=identity,
                operation=snapshot.claim.operation.value,
                work_id=snapshot.claim.id,
                user_id=snapshot.claim.user_id,
                lease_token=snapshot.claim.token,
                input_revision=snapshot.revision,
                prompt_fingerprint=snapshot.prompt_fingerprint,
                prompt_version=snapshot.prompt_version,
                model=model,
                outcome="unknown",
                usage=metadata.model_dump(mode="json") if metadata else None,
            )
        )
        self.session.commit()
        return identity

    def finish(self, attempt_id: str, *, outcome: str, usage: ProviderUsage) -> None:
        self.session.execute(
            update(ProviderAttempt)
            .where(ProviderAttempt.id == attempt_id)
            .values(
                outcome=outcome,
                usage=usage.model_dump(mode="json"),
                finished_at=datetime.now(UTC),
            )
        )
        self.session.commit()
