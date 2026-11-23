"""Regressions for the production period invalidation policy."""

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime
from unittest.mock import Mock

import pytest

from app.services.coaching.context_builder import PeriodContext
from app.services.coaching.period_planner import PeriodPlanner
from app.services.coaching.prompts import PROMPT_VERSION

TODAY = date(2026, 12, 2)


@dataclass
class PeriodRow:
    period_type: str
    period_start: date
    status: str = "ready"
    source_hash: str = "same-inputs"
    is_final: bool = True
    prompt_version: str = PROMPT_VERSION
    summary: str = "Keep the published interpretation."
    metrics: dict | None = None


def setup(*, pending=False, ready=True, source_hash="same-inputs", final=True):
    repository, contexts = Mock(), Mock()
    repository.list_users_with_recent_notes.return_value = [1]
    repository.list_recent_note_activity_dates.return_value = [
        datetime(2026, 11, 30, tzinfo=UTC)
    ]
    rows = {
        "week": PeriodRow("week", date(2026, 11, 30)),
        "month": PeriodRow("month", date(2026, 11, 1)),
    }
    repository.get_or_create_period.side_effect = lambda **kwargs: rows[
        kwargs["period_type"]
    ]
    contexts.build_period_context.side_effect = lambda **kwargs: PeriodContext(
        {"period_type": kwargs["period_type"]}, source_hash, final, pending, ready
    )
    return (
        PeriodPlanner(repository, contexts, lambda: TODAY),
        repository,
        contexts,
        rows,
    )


@pytest.mark.parametrize("pending,ready", [(True, True), (False, False)])
def test_periods_wait_for_ready_children_without_creating_work(pending, ready):
    planner, repository, _, _ = setup(pending=pending, ready=ready)
    assert planner.plan(user_id=1) == []
    repository.get_or_create_period.assert_not_called()


def test_unchanged_periods_finalize_once_when_the_window_ends():
    planner, repository, _, rows = setup(final=False)
    for row in rows.values():
        row.is_final = False
    assert planner.plan(user_id=1) == []
    planner.context_builder.build_period_context.side_effect = (
        lambda **kwargs: PeriodContext({}, "same-inputs", True, False, True)
    )
    assert [kind for _, kind, _ in planner.plan(user_id=1)] == ["week", "month"]
    for row in rows.values():
        row.is_final = True
    repository.mark_period_pending.reset_mock()
    assert planner.plan(user_id=1) == []
    repository.mark_period_pending.assert_not_called()


def test_failed_reviews_retry_only_after_relevant_inputs_change():
    planner, repository, contexts, rows = setup()
    for row in rows.values():
        row.status = "failed"
    assert planner.plan(user_id=1) == []
    contexts.build_period_context.side_effect = lambda **kwargs: PeriodContext(
        {}, "changed-inputs", True, False, True
    )
    assert len(planner.plan(user_id=1)) == 2
    assert repository.mark_period_pending.call_count == 2


@pytest.mark.parametrize("child_changed", [False, True])
def test_closed_periods_preserve_outside_changes_but_requeue_changed_daily_children(
    child_changed,
):
    planner, repository, contexts, rows = setup(source_hash="outside-week-changed")
    metrics = {
        "hierarchy": {
            "days": [{"date": "2026-11-30", "input_revisions": {"10": "saved"}}]
        }
    }
    for row in rows.values():
        row.metrics = deepcopy(metrics)
    current = deepcopy(metrics)
    if child_changed:
        current["hierarchy"]["days"][0]["input_revisions"]["10"] = "replaced"
    contexts.build_period_context.side_effect = lambda **kwargs: PeriodContext(
        {}, "changed-parent", True, False, True, current
    )
    assert len(planner.plan(user_id=1)) == (2 if child_changed else 0)
    assert repository.mark_period_pending.call_count == (2 if child_changed else 0)
    assert all(
        row.summary == "Keep the published interpretation." for row in rows.values()
    )


def test_cached_handoff_upgrade_preserves_legacy_prose_without_regeneration():
    planner, repository, contexts, rows = setup(source_hash="new-handoff")
    for row in rows.values():
        row.prompt_version = "legacy"
    repository.has_new_coaching_notes.return_value = False
    metrics = {"hierarchy": {"days": []}}
    contexts.build_period_context.side_effect = lambda **kwargs: PeriodContext(
        {}, "new-handoff", True, False, True, metrics
    )
    assert planner.plan(user_id=1) == []
    assert rows["week"].metrics == metrics
    assert all(
        row.summary == "Keep the published interpretation." for row in rows.values()
    )
    repository.mark_period_pending.assert_not_called()
