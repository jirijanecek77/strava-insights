"""Bounded graph control flow; durable state belongs exclusively to application rows."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from pydantic import ValidationError

from app.services.ai.contracts import (
    DeferredInputs,
    GeneratedResult,
    InputSnapshot,
    ObsoleteWork,
    Operation,
    PlanResult,
    RejectedPlan,
    WorkClaim,
)
from app.services.coaching.llm_client import LlmError, LlmRateLimitedError
from app.services.planning.policy import InsufficientTrainingData, validate_plan

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    activity_notes_generated: int = 0
    period_summaries_generated: int = 0
    training_plans_generated: int = 0
    failures: int = 0
    rate_limited: bool = False
    skipped_reason: str | None = None
    periods_planned: list = field(default_factory=list)
    provider_calls: int = 0
    work_items: int = 0
    obsolete: int = 0
    insufficient_data: int = 0


@dataclass
class WorkflowState:
    stats: RunStats
    claim: WorkClaim | None = None
    snapshot: InputSnapshot | None = None
    result: GeneratedResult | None = None
    error: Exception | None = None
    route: str = "end"
    planning_called: bool = False


class AiWorkflow:
    def __init__(self, repository, provider, period_planner, *, today=None):
        self.repository, self.provider, self.period_planner = (
            repository,
            provider,
            period_planner,
        )
        self.today = today or (lambda timezone: datetime.now(ZoneInfo(timezone)).date())

    def run(
        self, *, user_id=None, call_budget=3, work_budget=50, planning_only=False
    ) -> RunStats:
        stats = RunStats()
        if not self.provider.is_configured:
            stats.skipped_reason = "llm_not_configured"
            return stats
        call_budget, work_budget = max(0, call_budget), max(0, work_budget)

        def select_work(state: WorkflowState):
            if stats.provider_calls >= call_budget or stats.rate_limited:
                return {"route": "end"}
            if stats.work_items >= work_budget:
                stats.skipped_reason = "work_budget_exhausted"
                return {"route": "end"}
            claim = None
            if not state.planning_called:
                claim = self.repository.claim("plan", user_id=user_id)
            if claim is None and not planning_only:
                claim = self.repository.claim("activity", user_id=user_id)
            if claim is None and not planning_only:
                stats.periods_planned.extend(self.period_planner.plan(user_id=user_id))
                claim = self.repository.claim("period", user_id=user_id)
            if claim is None:
                return {"route": "end"}
            stats.work_items += 1
            return {
                "claim": claim,
                "snapshot": None,
                "result": None,
                "error": None,
                "route": "prepare",
            }

        def prepare(state):
            try:
                snapshot = self.repository.prepare(
                    state.claim, self.today(state.claim.timezone)
                )
                if state.claim.operation == Operation.PLAN and snapshot.context.dates[
                    -1
                ] <= self.today(state.claim.timezone):
                    raise InsufficientTrainingData(
                        "The requested planning window expired"
                    )
                return {"snapshot": snapshot, "route": "generate"}
            except Exception as exc:
                return {"error": exc, "route": "failure"}

        def generate(state):
            before = self.provider.attempts
            try:
                return {
                    "result": self.provider.generate(state.snapshot),
                    "route": "validate",
                }
            except Exception as exc:
                return {"error": exc, "route": "failure"}
            finally:
                calls = self.provider.attempts - before
                stats.provider_calls += calls

        def after_generation(state):
            return {
                "planning_called": state.planning_called
                or state.claim.operation == Operation.PLAN,
                "route": state.route,
            }

        def validate(state):
            try:
                if state.claim.operation == Operation.PLAN:
                    if not isinstance(state.result.value, PlanResult):
                        raise ValueError("Wrong running forecast result type")
                    try:
                        validate_plan(
                            state.result.value.model_dump(mode="json"),
                            state.snapshot.context.model_dump(mode="json"),
                        )
                    except ValueError as exc:
                        if state.result.attempt_id:
                            self.repository.record_outcome(
                                state.result.attempt_id, "domain_failure"
                            )
                        raise RejectedPlan(str(exc)) from None
                return {"route": "publish"}
            except Exception as exc:
                return {"error": exc, "route": "failure"}

        def publish(state):
            try:
                if self.repository.publish(
                    state.snapshot, state.result, today=self.today(state.claim.timezone)
                ):
                    if state.claim.operation == Operation.ACTIVITY:
                        stats.activity_notes_generated += 1
                    elif state.claim.operation == Operation.PLAN:
                        stats.training_plans_generated += 1
                    else:
                        stats.period_summaries_generated += 1
                else:
                    stats.obsolete += 1
                    if state.result.attempt_id:
                        self.repository.record_outcome(
                            state.result.attempt_id, "obsolete_publication"
                        )
                return {"route": "select"}
            except Exception as exc:
                return {"error": exc, "route": "failure"}

        def failure(state):
            exc, claim = state.error, state.claim
            kwargs = {"snapshot": state.snapshot}
            if isinstance(exc, ObsoleteWork):
                stats.obsolete += 1
                return {"route": "select"}
            if isinstance(exc, LlmRateLimitedError):
                stats.rate_limited = True
                kwargs.update(
                    status="pending",
                    error="Provider rate limit",
                    delay=exc.retry_after_seconds,
                )
            elif isinstance(exc, DeferredInputs):
                kwargs.update(
                    status="pending",
                    error="Waiting for prepared child/source inputs",
                    delay=300,
                )
            elif isinstance(exc, InsufficientTrainingData):
                stats.insufficient_data += 1
                kwargs.update(status="insufficient_data", error=str(exc))
            else:
                stats.failures += 1
                attempts = claim.attempt_count + 1
                # Pydantic/provider/unexpected exception strings may contain athlete payloads.
                safe = (
                    str(exc)
                    if isinstance(exc, (LlmError, RejectedPlan))
                    else "AI generation failed validation or execution"
                )
                kwargs.update(
                    status="failed" if attempts >= 5 else "pending",
                    error=safe,
                    failure=True,
                    delay=(
                        None if attempts >= 5 else min(21600, 300 * 2 ** (attempts - 1))
                    ),
                )
            self.repository.finish(claim, **kwargs)
            logger.info(
                "AI work deferred or failed",
                extra={
                    "ai.operation": claim.operation.value,
                    "ai.work_id": claim.id,
                    "user.id": claim.user_id,
                    "error.class": type(exc).__name__,
                    "ai.outcome": kwargs["status"],
                },
            )
            return {"route": "select"}

        graph = StateGraph(WorkflowState)
        nodes = {
            "select": select_work,
            "prepare": prepare,
            "generate": generate,
            "after_generation": after_generation,
            "validate": validate,
            "publish": publish,
            "failure": failure,
        }
        for name, node in nodes.items():
            graph.add_node(name, node)
        graph.add_edge(START, "select")
        graph.add_edge("generate", "after_generation")
        for name in (
            "select",
            "prepare",
            "after_generation",
            "validate",
            "publish",
            "failure",
        ):
            graph.add_conditional_edges(
                name,
                lambda state: state.route,
                {**{key: key for key in nodes}, "end": END},
            )
        compiled = graph.compile()  # No checkpointer/store or node/LLM retry policies.
        with tracing_context(enabled=False):
            compiled.invoke(
                WorkflowState(stats),
                config={
                    "recursion_limit": max(16, work_budget * 8 + 8),
                    "callbacks": [],
                },
            )
        logger.info(
            "AI workflow run finished",
            extra={
                "user.id": user_id,
                "ai.provider_calls": stats.provider_calls,
                "ai.work_items": stats.work_items,
                "ai.obsolete": stats.obsolete,
                "failures": stats.failures,
                "rate_limited": stats.rate_limited,
                "skipped_reason": stats.skipped_reason,
            },
        )
        return stats
