"""Prepare typed snapshots and operation-scoped invalidation revisions locally."""

from app.models import ActivityCoachingEvidence
from app.services.ai.contracts import (
    ActivityContext,
    Context,
    DeferredInputs,
    InputSnapshot,
    Operation,
    PeriodContextData,
    PlanningContext,
    WorkClaim,
)
from app.services.coaching.context_builder import CoachingContextBuilder
from app.services.coaching.contracts import ActivityFacts, HierarchyFacts
from app.services.coaching.evidence import fingerprint
from app.services.coaching.prompts import (
    ACTIVITY_PROMPT_VERSION,
    PROMPT_VERSION,
    build_activity_prompt,
    build_period_prompt,
)
from app.services.planning.policy import PROMPT_VERSION as PLAN_VERSION
from app.services.planning.policy import build_prompt


def period_revision(context: dict, metrics: dict) -> str:
    # Daily child revisions refer to the actual dates. The top-level week revision
    # also covers outside-month dates and is only a debugging fingerprint.
    projected = {key: value for key, value in metrics.items() if key != "hierarchy"}
    projected["days"] = metrics["hierarchy"]["days"]
    if context["period_type"] == "week":
        interpretations = context["activities"]
    else:
        interpretations = [row for row in context["weeks"] if not row["partial_week"]]
    return fingerprint([projected, interpretations])


class SnapshotBuilder:
    def __init__(self, session, coaching, planning):
        self.session = session
        self.coaching = coaching
        self.planning = planning
        self.contexts = CoachingContextBuilder(coaching)

    def build(self, claim: WorkClaim, today) -> InputSnapshot:
        handoff: ActivityFacts | HierarchyFacts | None = None
        metrics: dict | None = None
        source_hash: str | None = None
        context: Context
        is_final = False
        if claim.operation == Operation.ACTIVITY:
            raw = self.contexts.build_activity_context(
                user_id=claim.user_id, activity_id=claim.activity_id
            )
            if raw is None:
                raise ValueError("Activity no longer exists")
            context = ActivityContext.model_validate(raw)
            stored = self.session.get(ActivityCoachingEvidence, claim.activity_id)
            handoff = ActivityFacts.model_validate(stored.facts)
            revision = fingerprint([raw, handoff.model_dump(mode="json")])
            system, user = build_activity_prompt(raw)
            version = ACTIVITY_PROMPT_VERSION
        elif claim.operation in {Operation.WEEK, Operation.MONTH}:
            period = self.contexts.build_period_context(
                user_id=claim.user_id,
                period_type=claim.operation.value,
                period_start=claim.period_start,
                today=today,
            )
            if period.has_pending_notes or not period.has_ready_notes:
                raise DeferredInputs("Waiting for child coaching evaluations")
            raw, metrics = period.context, period.metrics
            context = PeriodContextData.model_validate(raw)
            handoff = HierarchyFacts.model_validate(metrics["hierarchy"])
            revision = period_revision(raw, metrics)
            source_hash, is_final = period.source_hash, period.is_final
            system, user = build_period_prompt(raw)
            version = PROMPT_VERSION
        else:
            request = {
                "context": (
                    claim.saved_context.model_dump(mode="json")
                    if claim.saved_context
                    else None
                ),
                "user_id": claim.user_id,
                "timezone": claim.timezone,
            }
            raw = self.planning.build_context(request, today)
            context = PlanningContext.model_validate(raw)
            revision = fingerprint(raw)
            if claim.last_error:
                raw = {**raw, "previous_attempt_error": claim.last_error}
            system, user = build_prompt(raw)
            version = PLAN_VERSION
        return InputSnapshot(
            claim,
            context,
            revision,
            fingerprint([system, user]),
            system,
            user,
            version,
            today,
            handoff=handoff,
            metrics=metrics,
            source_hash=source_hash,
            is_final=is_final,
        )
