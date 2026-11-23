"""Fenced application publication. Source triggers and publishers use the same lock."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import exists, select, text, update

from app.models import (
    ActivityCoachingNote,
    PeriodCoachingSummary,
    SyncJob,
    TrainingPlanRequest,
    User,
)
from app.repositories import CoachingRepository
from app.services.ai.attempts import ProviderAttempt
from app.services.ai.contracts import (
    ActivityResult,
    DeferredInputs,
    GeneratedResult,
    InputSnapshot,
    ObsoleteWork,
    Operation,
    PeriodResult,
    PlanningContext,
    PlanResult,
    WorkClaim,
)
from app.services.ai.snapshots import SnapshotBuilder
from app.services.planning.policy import validate_plan
from app.services.planning.repository import PlanningRepository


class AiWorkRepository:
    def __init__(self, session):
        self.session = session
        self.coaching = CoachingRepository(session)
        self.planning = PlanningRepository(session)
        self.snapshots = SnapshotBuilder(session, self.coaching, self.planning)

    def lock(self, user_id):
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(74022, :user_id)"), {"user_id": user_id}
        )

    def claim(self, kind: str, *, user_id=None) -> WorkClaim | None:
        if kind == "plan":
            row = self.planning.claim(user_id=user_id)
            if row is None:
                return None
            try:
                saved = (
                    PlanningContext.model_validate(row["context"])
                    if row["context"]
                    else None
                )
            except ValidationError:
                self.planning.finish(
                    row,
                    status="failed",
                    error="Obsolete planning context; request a fresh forecast",
                )
                return None
            return WorkClaim(
                Operation.PLAN,
                row["id"],
                row["user_id"],
                row["lease_token"],
                row["attempt_count"],
                timezone=row["timezone"],
                saved_context=saved,
                last_error=row["last_error"],
            )
        row = (
            self.coaching.claim_next_activity_note(user_id=user_id)
            if kind == "activity"
            else self.coaching.claim_next_period(user_id=user_id)
        )
        if row is None:
            return None
        return WorkClaim(
            Operation.ACTIVITY if kind == "activity" else Operation(row.period_type),
            row.id,
            row.user_id,
            row.lease_token,
            row.attempt_count,
            activity_id=row.activity_id if kind == "activity" else None,
            period_start=row.period_start if kind != "activity" else None,
        )

    def _owned(self, claim: WorkClaim):
        self.lock(claim.user_id)
        self.session.expire_all()
        if claim.operation == Operation.PLAN:
            return self.planning._owned(self._request(claim))
        model = (
            ActivityCoachingNote
            if claim.operation == Operation.ACTIVITY
            else PeriodCoachingSummary
        )
        row = (
            self.session.query(model)
            .filter(model.id == claim.id, model.user_id == claim.user_id)
            .populate_existing()
            .with_for_update()
            .one_or_none()
        )
        if (
            row is None
            or row.status != "generating"
            or row.lease_token != claim.token
            or row.lease_expires_at is None
            or row.lease_expires_at <= datetime.now(UTC)
        ):
            self.session.rollback()
            return None
        return row

    def owns(self, claim: WorkClaim) -> bool:
        return self._owned(claim) is not None

    def prepare(self, claim: WorkClaim, today) -> InputSnapshot:
        row = self._owned(claim)
        if row is None:
            raise ObsoleteWork("Claim expired or was replaced")
        if self.session.scalar(
            select(SyncJob.id)
            .where(
                SyncJob.user_id == claim.user_id,
                SyncJob.status.in_(["queued", "running"]),
            )
            .limit(1)
        ):
            raise DeferredInputs("Waiting for import preparation")
        snapshot = self.snapshots.build(claim, today)
        row.input_revision = snapshot.revision
        if claim.operation == Operation.PLAN:
            row.context_json = snapshot.context.model_dump(mode="json")
            row.target_start = snapshot.context.dates[0]
            row.source_hash = snapshot.prompt_fingerprint
            row.prompt_version = snapshot.prompt_version
        self.session.commit()
        return snapshot

    def publish(
        self, snapshot: InputSnapshot, result: GeneratedResult, *, today
    ) -> bool:
        claim = snapshot.claim
        row = self._owned(claim)
        if row is None:
            return False
        active_sync = self.session.scalar(
            select(SyncJob.id)
            .where(
                SyncJob.user_id == claim.user_id,
                SyncJob.status.in_(["queued", "running"]),
            )
            .limit(1)
        )
        user_active = self.session.scalar(
            select(User.is_active).where(User.id == claim.user_id)
        )
        if active_sync or user_active is not True:
            self._obsolete(row)
            return False
        try:
            current_claim = (
                replace(
                    claim,
                    saved_context=PlanningContext.model_validate(row.context_json),
                )
                if claim.operation == Operation.PLAN
                else claim
            )
            current = self.snapshots.build(
                current_claim,
                today if claim.operation == Operation.PLAN else snapshot.prepared_on,
            )
        except (DeferredInputs, ValueError):
            self._obsolete(row)
            return False
        if (
            current.revision != snapshot.revision
            or row.input_revision != snapshot.revision
        ):
            self._obsolete(row)
            return False
        if row.lease_expires_at <= datetime.now(UTC):
            self.session.rollback()
            return False
        if claim.operation == Operation.PLAN:
            if not isinstance(result.value, PlanResult):
                raise ValueError("Wrong result type for running forecast")
            days = validate_plan(
                result.value.model_dump(mode="json"),
                snapshot.context.model_dump(mode="json"),
            )
            return self.planning.publish(
                self._request(claim), days, model=result.model, today=today
            )
        row.lease_token = None
        if claim.operation == Operation.ACTIVITY:
            if not isinstance(result.value, ActivityResult):
                raise ValueError("Wrong result type for activity coaching")
            self.coaching.mark_activity_note_ready(
                row,
                **result.value.model_dump(),
                model=result.model,
                prompt_version=snapshot.prompt_version
            )
        else:
            if not isinstance(result.value, PeriodResult):
                raise ValueError("Wrong result type for period coaching")
            self.coaching.mark_period_ready(
                row,
                **result.value.model_dump(),
                source_hash=snapshot.source_hash,
                is_final=snapshot.is_final,
                model=result.model,
                prompt_version=snapshot.prompt_version,
                metrics=snapshot.metrics
            )
        return True

    def finish(
        self,
        claim: WorkClaim,
        *,
        status: str,
        error: str | None = None,
        delay: int | None = None,
        failure: bool = False,
        snapshot: InputSnapshot | None = None
    ):
        row = self._owned(claim)
        if row is None:
            return False
        if failure and snapshot is not None:
            try:
                current_claim = (
                    replace(
                        claim,
                        saved_context=PlanningContext.model_validate(row.context_json),
                    )
                    if claim.operation == Operation.PLAN
                    else claim
                )
                current = self.snapshots.build(current_claim, snapshot.prepared_on)
            except (DeferredInputs, ValueError):
                self._obsolete(row)
                return False
            if current.revision != snapshot.revision:
                self._obsolete(row)
                return False
        row.status = status
        row.attempt_count = claim.attempt_count + int(failure)
        row.last_error = error
        row.next_attempt_at = (
            datetime.now(UTC) + timedelta(seconds=delay) if delay is not None else None
        )
        row.lease_token = row.lease_expires_at = None
        if (
            snapshot
            and claim.operation in {Operation.WEEK, Operation.MONTH}
            and status == "failed"
        ):
            row.source_hash = snapshot.source_hash
        self.session.commit()
        return True

    def _obsolete(self, row):
        row.status = "pending"
        row.attempt_count = 0
        row.last_error = None
        row.lease_token = row.lease_expires_at = None
        row.next_attempt_at = None
        self.session.commit()

    def record_outcome(self, attempt_id: str, outcome: str) -> None:
        self.session.execute(
            update(ProviderAttempt)
            .where(ProviderAttempt.id == attempt_id)
            .values(outcome=outcome)
        )
        self.session.commit()

    @staticmethod
    def _request(claim):
        return {"id": claim.id, "user_id": claim.user_id, "lease_token": claim.token}
