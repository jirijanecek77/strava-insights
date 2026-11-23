from dataclasses import replace
from datetime import date
from unittest.mock import Mock

import pytest
from ai_fixtures import snapshot_for

from app.infrastructure.ai.langgraph_workflow import AiWorkflow
from app.services.ai.contracts import (
    ActivityResult,
    GeneratedResult,
    Operation,
    PlanResult,
    ProviderUsage,
    WorkClaim,
)


def fixture():
    snapshot = snapshot_for("plan-supported")
    distances = {0: 8.5, 2: 8.5, 5: 8.2}
    days = []
    for index, day in enumerate(snapshot.context.dates):
        run = index in distances
        days.append(
            {
                "date": str(day),
                "kind": "run" if run else "rest",
                "focus": "easy" if run else "rest",
                "distance_km": distances.get(index),
                "pace_seconds_per_km": 345 if run else None,
                "heart_rate_bpm": 140 if run else None,
                "rationale": "Bounded aerobic running.",
            }
        )
    return snapshot, PlanResult.model_validate({"days": days})


class Provider:
    is_configured = True
    attempts = 0

    def __init__(self, plan):
        self.plan = plan
        self.operations = []

    def generate(self, snapshot):
        self.attempts += 1
        self.operations.append(snapshot.claim.operation)
        value = (
            self.plan
            if snapshot.claim.operation == Operation.PLAN
            else ActivityResult(
                description="Run", summary="Aerobic", recommendation="Recover"
            )
        )
        return GeneratedResult(value, "stub", ProviderUsage(), "attempt-id")


def test_at_most_one_planning_http_attempt_per_graph_run_even_with_remaining_budget():
    snapshot, plan = fixture()
    repo, planner = Mock(), Mock()
    planner.plan.return_value = []
    remaining = [snapshot.claim, replace(snapshot.claim, id=99)]
    repo.claim.side_effect = lambda kind, **kwargs: (
        remaining.pop(0) if kind == "plan" and remaining else None
    )
    repo.prepare.return_value = snapshot
    repo.publish.return_value = True
    provider = Provider(plan)
    stats = AiWorkflow(repo, provider, planner, today=lambda _: date(2026, 11, 23)).run(
        call_budget=5
    )
    assert stats.training_plans_generated == 1 and stats.provider_calls == 1
    assert len(remaining) == 1


def test_recent_note_finishes_before_waiting_plan_in_the_same_shared_budget():
    snapshot, plan = fixture()
    repo, planner = Mock(), Mock()
    planner.plan.return_value = []
    note = WorkClaim(
        Operation.ACTIVITY, 8, snapshot.claim.user_id, "note", 0, activity_id=8
    )
    state = {"ready": False, "claimed": False, "planned": False}

    def claim(kind, **kwargs):
        if kind == "activity" and not state["claimed"]:
            state["claimed"] = True
            return note
        if kind == "plan" and state["ready"] and not state["planned"]:
            state["planned"] = True
            return snapshot.claim
        return None

    repo.claim.side_effect = claim
    repo.prepare.side_effect = lambda claim, today: replace(snapshot, claim=claim)

    def publish(current, *args, **kwargs):
        if current.claim.operation == Operation.ACTIVITY:
            state["ready"] = True
        return True

    repo.publish.side_effect = publish
    provider = Provider(plan)
    stats = AiWorkflow(repo, provider, planner, today=lambda _: date(2026, 11, 23)).run(
        call_budget=2
    )
    assert provider.operations == [Operation.ACTIVITY, Operation.PLAN]
    assert stats.activity_notes_generated == stats.training_plans_generated == 1


@pytest.mark.parametrize(
    "attempt_count,status,delay", [(0, "pending", 300), (4, "failed", None)]
)
def test_structured_but_unsafe_plan_is_recorded_as_domain_failure_with_no_publication(
    attempt_count, status, delay
):
    snapshot, plan = fixture()
    snapshot = replace(
        snapshot, claim=replace(snapshot.claim, attempt_count=attempt_count)
    )
    invalid = plan.model_dump()
    invalid["days"][0]["distance_km"] = 100
    repo, planner = Mock(), Mock()
    repo.claim.return_value = snapshot.claim
    repo.prepare.return_value = snapshot
    provider = Provider(PlanResult.model_validate(invalid))
    stats = AiWorkflow(repo, provider, planner, today=lambda _: date(2026, 11, 23)).run(
        call_budget=1
    )
    assert stats.failures == 1 and stats.provider_calls == 1
    repo.record_outcome.assert_called_once_with("attempt-id", "domain_failure")
    repo.publish.assert_not_called()
    assert repo.finish.call_args.kwargs["failure"] is True
    assert repo.finish.call_args.kwargs["status"] == status
    assert repo.finish.call_args.kwargs["delay"] == delay


def test_plan_retry_prompt_receives_validation_feedback_without_changing_saved_facts():
    from app.services.ai.snapshots import SnapshotBuilder

    snapshot, _ = fixture()
    planning = Mock()
    planning.build_context.return_value = snapshot.context.model_dump(mode="json")
    claim = replace(
        snapshot.claim, last_error="Target exceeds the current running bound"
    )
    retry = SnapshotBuilder(None, None, planning).build(claim, date(2026, 11, 23))
    assert "Target exceeds the current running bound" in retry.user_prompt
    assert "previous_attempt_error" not in retry.context.model_dump()
    assert retry.context == snapshot.context
