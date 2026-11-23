"""Publication races with mocked persistence; no physical database is opened."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models import ActivityCoachingNote, PeriodCoachingSummary
from app.repositories import CoachingRepository
from app.services.ai.contracts import (
    ActivityResult,
    GeneratedResult,
    InputSnapshot,
    Operation,
    PeriodResult,
    ProviderUsage,
    WorkClaim,
)
from app.services.ai.repository import AiWorkRepository
from app.services.ai.snapshots import period_revision


@pytest.fixture
def storage():
    session = Mock()
    query = session.query.return_value
    query.filter.return_value = query.populate_existing.return_value = (
        query.with_for_update.return_value
    ) = query
    row = ActivityCoachingNote(
        id=4,
        user_id=2,
        activity_id=8,
        status="generating",
        lease_token="current",
        input_revision="revision",
        attempt_count=0,
        summary="Keep published summary",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    query.one_or_none.return_value = row
    session.scalar.side_effect = [None, True]
    repo = AiWorkRepository(session)
    repo.snapshots = Mock()
    claim = WorkClaim(Operation.ACTIVITY, 4, 2, "current", 0, activity_id=8)
    snapshot = InputSnapshot(
        claim, Mock(), "revision", "prompt", "system", "user", "7", date(2026, 11, 23)
    )
    repo.snapshots.build.return_value = snapshot
    result = GeneratedResult(
        ActivityResult(
            description="New description",
            summary="New summary",
            recommendation="Recover",
        ),
        "test",
        ProviderUsage(),
    )
    return repo, session, row, snapshot, result


@pytest.mark.parametrize("race", ["new_owner", "expired", "missing"])
def test_obsolete_owner_cannot_publish_or_change_retry_failure_state(storage, race):
    repo, session, row, snapshot, result = storage
    if race == "new_owner":
        row.lease_token = "replacement"
    elif race == "expired":
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    else:
        session.query.return_value.one_or_none.return_value = None
    assert not repo.publish(snapshot, result, today=date(2026, 11, 23))
    assert not repo.finish(
        snapshot.claim, status="failed", failure=True, error="old failure"
    )
    assert row.status == "generating" and row.summary == "Keep published summary"
    session.commit.assert_not_called()


def test_changed_source_rejects_result_and_preserves_previous_publication(storage):
    repo, session, row, snapshot, result = storage
    repo.snapshots.build.return_value = replace(snapshot, revision="new revision")
    assert not repo.publish(snapshot, result, today=date(2026, 11, 23))
    assert row.status == "pending" and row.lease_token is None
    assert row.summary == "Keep published summary"
    assert "pg_advisory_xact_lock" in str(session.execute.call_args_list[0].args[0])


def test_current_owner_publishes_under_same_source_lock(storage):
    repo, session, row, snapshot, result = storage
    repo.coaching._save_activity_evaluation = Mock()
    assert repo.publish(snapshot, result, today=date(2026, 11, 23))
    assert row.status == "ready" and row.summary == "New summary"
    repo.coaching._save_activity_evaluation.assert_called_once()
    session.commit.assert_called_once()


def test_failure_for_replaced_inputs_does_not_terminally_fail_the_fresh_revision(
    storage,
):
    repo, session, row, snapshot, result = storage
    row.attempt_count = 4
    snapshot = replace(snapshot, claim=replace(snapshot.claim, attempt_count=4))
    repo.snapshots.build.return_value = replace(snapshot, revision="changed inputs")
    repo.finish(
        snapshot.claim,
        status="failed",
        error="Old invalid answer",
        failure=True,
        snapshot=snapshot,
    )
    assert row.status == "pending" and row.attempt_count == 0
    assert row.summary == "Keep published summary"


def test_boundary_week_debug_revision_and_outside_prose_do_not_invalidate_month():
    metrics = {
        "totals_by_sport": {"Run": {"distance_km": 10}},
        "hierarchy": {
            "input_revisions": {"week": "old"},
            "days": [{"date": "2026-11-30", "input_revisions": {"8": "ready-1"}}],
        },
    }
    context = {
        "period_type": "month",
        "weeks": [{"partial_week": True, "summary": "Whole week, including December"}],
    }
    original = period_revision(context, metrics)
    metrics["hierarchy"]["input_revisions"]["week"] = "December changed"
    context["weeks"][0]["summary"] = "New December text"
    assert period_revision(context, metrics) == original
    metrics["hierarchy"]["days"][0]["input_revisions"]["8"] = "changed November child"
    assert period_revision(context, metrics) != original


@pytest.mark.parametrize("kind", [Operation.WEEK, Operation.MONTH])
@pytest.mark.parametrize("race", ["owner", "revision", "none"])
def test_period_publication_fences_owners_and_children_and_preserves_handoffs(
    storage, kind, race
):
    repo, session, old, snapshot, result = storage
    row = PeriodCoachingSummary(
        id=4,
        user_id=2,
        period_type=kind.value,
        period_start=date(2026, 11, 1),
        status="generating",
        lease_token="current",
        input_revision="revision",
        summary="Keep published summary",
        metrics={"old": "preserve"},
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    session.query.return_value.one_or_none.return_value = row
    snapshot = replace(
        snapshot,
        claim=replace(
            snapshot.claim,
            operation=kind,
            activity_id=None,
            period_start=date(2026, 11, 1),
        ),
        metrics={"new": "handoff"},
        source_hash="source",
    )
    repo.snapshots.build.return_value = replace(
        snapshot, revision="new" if race == "revision" else "revision"
    )
    if race == "owner":
        row.lease_token = "replacement"
    result = replace(
        result, value=PeriodResult(summary="New summary", recommendation="Recover")
    )
    published = repo.publish(snapshot, result, today=date(2026, 11, 23))
    assert published == (race == "none")
    assert row.summary == ("New summary" if published else "Keep published summary")
    assert row.metrics == ({"new": "handoff"} if published else {"old": "preserve"})


def test_reclaimed_coaching_work_gets_a_fresh_owner_token():
    session, query = Mock(), Mock()
    row = ActivityCoachingNote(
        id=1, user_id=2, activity_id=3, status="pending", lease_token="old-owner"
    )
    query.with_for_update.return_value.first.return_value = row
    assert CoachingRepository(session)._claim(query, ActivityCoachingNote) is row
    assert row.lease_token != "old-owner" and len(row.lease_token) == 36
    assert row.status == "generating"
