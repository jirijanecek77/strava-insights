from dataclasses import replace
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.infrastructure.ai.langgraph_workflow import AiWorkflow
from app.services.ai.contracts import (
    ActivityResult,
    DeferredInputs,
    GeneratedResult,
    InputSnapshot,
    Operation,
    ProviderUsage,
    WorkClaim,
)
from app.services.coaching.llm_client import LlmRateLimitedError
from app.services.planning.policy import InsufficientTrainingData


class Provider:
    is_configured = True
    model = "stub"

    def __init__(self, error=None):
        self.attempts = 0
        self.error = error

    def generate(self, snapshot):
        self.attempts += 1
        if self.error:
            raise self.error
        return GeneratedResult(
            ActivityResult(
                description="Run.", summary="Aerobic.", recommendation="Recover."
            ),
            self.model,
            ProviderUsage(),
        )


def setup(kinds):
    repo = Mock()
    pending = {kind: [] for kind in ("plan", "activity", "period")}
    for i, kind in enumerate(kinds):
        pending["period" if kind in ("week", "month") else kind].append(
            WorkClaim(Operation(kind), i, 1, "token", 0, activity_id=i)
        )
    repo.claim.side_effect = lambda kind, **kwargs: (
        pending[kind].pop(0) if pending[kind] else None
    )
    repo.prepare.side_effect = lambda claim, today: InputSnapshot(
        claim,
        SimpleNamespace(dates=[date(2026, 12, 1)]),
        "rev",
        "prompt",
        "system",
        "input",
        "7",
        date(2026, 11, 23),
    )
    repo.publish.return_value = True
    planner = Mock()
    planner.plan.return_value = []
    return repo, planner


def test_graph_reselects_after_activities_then_weeks_then_months_with_actual_call_budget():
    repo, planner = setup(["activity", "activity", "week", "month"])
    provider = Provider()
    stats = AiWorkflow(repo, provider, planner, today=lambda _: date(2026, 11, 23)).run(
        call_budget=4
    )
    assert (
        stats.activity_notes_generated,
        stats.period_summaries_generated,
        stats.provider_calls,
    ) == (2, 2, 4)
    assert [call.args[0].claim.operation for call in repo.publish.call_args_list] == [
        Operation.ACTIVITY,
        Operation.ACTIVITY,
        Operation.WEEK,
        Operation.MONTH,
    ]
    assert planner.plan.call_count == 2


def test_many_no_call_items_stop_at_separate_work_limit():
    repo, planner = setup(["activity"] * 1000)
    repo.prepare.side_effect = DeferredInputs("Wait")
    provider = Provider()
    stats = AiWorkflow(repo, provider, planner).run(call_budget=3, work_budget=15)
    assert stats.work_items == 15 and provider.attempts == 0
    assert stats.skipped_reason == "work_budget_exhausted"
    assert repo.finish.call_count == 15


def test_rate_limit_counts_request_defers_without_failure_increment_and_stops():
    repo, planner = setup(["activity"] * 4)
    stats = AiWorkflow(
        repo, Provider(LlmRateLimitedError("Limit", retry_after_seconds=30)), planner
    ).run(call_budget=4)
    assert stats.rate_limited and stats.provider_calls == 1
    assert stats.failures == 0
    assert repo.finish.call_args.kwargs["delay"] == 30
    assert "failure" not in repo.finish.call_args.kwargs


def test_rejected_publication_returns_to_selection_without_hidden_model_call():
    repo, planner = setup(["activity", "activity"])
    repo.publish.side_effect = [False, True]
    stats = AiWorkflow(repo, Provider(), planner).run(call_budget=2)
    assert (
        stats.provider_calls == 2
        and stats.activity_notes_generated == 1
        and stats.obsolete == 1
    )


def test_insufficient_plan_allows_notes_without_spending_reserved_provider_call():
    repo, planner = setup(["plan", "activity"])
    original = repo.prepare.side_effect
    repo.prepare.side_effect = lambda claim, today: (
        (_ for _ in ()).throw(InsufficientTrainingData("Not enough running history"))
        if claim.operation == Operation.PLAN
        else original(claim, today)
    )
    stats = AiWorkflow(repo, Provider(), planner).run(call_budget=1)
    assert (
        stats.insufficient_data == 1
        and stats.activity_notes_generated == 1
        and stats.provider_calls == 1
    )


def test_manual_scope_and_missing_key_preserve_queue_semantics():
    repo, planner = setup(["activity"])
    provider = Provider()
    stats = AiWorkflow(repo, provider, planner).run(user_id=3, planning_only=True)
    assert stats.provider_calls == 0
    assert all(
        call.args[0] == "plan" and call.kwargs["user_id"] == 3
        for call in repo.claim.call_args_list
    )
    repo.reset_mock()
    provider.is_configured = False
    assert (
        AiWorkflow(repo, provider, planner).run().skipped_reason == "llm_not_configured"
    )
    repo.claim.assert_not_called()


def test_unexpected_provider_value_errors_do_not_persist_or_log_private_payloads():
    repo, planner = setup(["activity"])
    stats = AiWorkflow(
        repo, Provider(ValueError("private athlete context and credential")), planner
    ).run(call_budget=1)
    assert stats.failures == 1
    assert "private" not in repo.finish.call_args.kwargs["error"]
