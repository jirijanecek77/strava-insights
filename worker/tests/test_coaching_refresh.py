"""Explicit summary regeneration with mocked storage and no provider calls."""

import pytest
from app import coaching_cli
from app.models import PeriodCoachingSummary
from app.repositories import CoachingRepository
from datetime import UTC, date, datetime
from sqlalchemy import and_
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, Mock


@pytest.fixture(autouse=True)
def preserve_process_logging(monkeypatch):
    monkeypatch.setattr(coaching_cli, "configure_logging", Mock())


def test_activity_regeneration_preserves_text_and_active_generation():
    session = Mock(spec=Session)
    repository = CoachingRepository(session)

    repository.enqueue_activity_note(user_id=4, activity_id=12, regenerate=True)

    statement = session.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (activity_id) DO UPDATE SET" in sql
    update, condition = sql.split("DO UPDATE SET", 1)[1].split(" WHERE ", 1)
    assert all(
        field in update
        for field in (
            "status",
            "attempt_count",
            "next_attempt_at",
            "lease_expires_at",
            "last_error",
        )
    )
    assert all(
        field not in update
        for field in ("description", "summary", "recommendation", "generated_at")
    )
    assert "activity_coaching_notes.status !=" in condition
    assert "activity_coaching_notes.user_id =" in condition
    assert "generating" in statement.compile().params.values()
    session.commit.assert_not_called()


def test_normal_enqueue_still_keeps_existing_notes():
    session = Mock(spec=Session)
    CoachingRepository(session).enqueue_activity_note(user_id=4, activity_id=12)
    sql = str(session.execute.call_args.args[0])
    assert "ON CONFLICT (activity_id) DO NOTHING" in sql


def test_recent_periods_are_bounded_and_requeued_without_erasing_results():
    session = Mock(spec=Session)
    query = Mock()
    for method in ("filter", "order_by", "limit", "with_for_update"):
        getattr(query, method).return_value = query
    session.query.return_value = query
    generated_at = datetime(2026, 11, 1, tzinfo=UTC)
    period = PeriodCoachingSummary(
        user_id=4,
        period_type="month",
        period_start=date(2026, 10, 1),
        status="failed",
        attempt_count=5,
        next_attempt_at=generated_at,
        lease_expires_at=generated_at,
        last_error="Old failure",
        summary="Stored summary",
        recommendation="Stored advice",
        generated_at=generated_at,
        metrics={"hierarchy": {"days": []}},
    )
    query.all.return_value = [period]

    count = CoachingRepository(session).requeue_latest_periods(
        user_id=4, period_type="month", count=3
    )

    assert count == 1
    query.limit.assert_called_once_with(3)
    query.with_for_update.assert_called_once_with(skip_locked=True)
    conditions = [
        condition for call in query.filter.call_args_list for condition in call.args
    ]
    sql = str(
        and_(*conditions).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "period_coaching_summaries.user_id = 4" in sql
    assert "period_coaching_summaries.period_type = 'month'" in sql
    assert "period_coaching_summaries.status != 'generating'" in sql
    assert "period_start DESC" in str(query.order_by.call_args.args[0])
    assert period.status == "pending" and period.attempt_count == 0
    assert period.next_attempt_at is None and period.lease_expires_at is None
    assert period.last_error is None
    assert (
            period.summary == "Stored summary" and period.recommendation == "Stored advice"
    )
    assert period.generated_at == generated_at
    assert period.metrics == {"hierarchy": {"days": []}}
    session.commit.assert_not_called()


def test_zero_period_count_does_not_select_history():
    session = Mock(spec=Session)
    assert (
            CoachingRepository(session).requeue_latest_periods(
                user_id=4, period_type="week", count=0
            )
            == 0
    )
    session.query.assert_not_called()


def test_regenerate_latest_cli_queues_all_levels_in_one_transaction(
        monkeypatch, capsys
):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    session_factory = Mock(return_value=context)
    repository = Mock(spec=CoachingRepository)
    repository.list_latest_activity_ids.return_value = [15, 14, 13]
    repository.requeue_latest_periods.side_effect = [2, 1]
    monkeypatch.setattr(coaching_cli, "SessionLocal", session_factory)
    monkeypatch.setattr(
        coaching_cli, "CoachingRepository", Mock(return_value=repository)
    )
    monkeypatch.setattr(coaching_cli, "configure_logging", Mock())
    generate = Mock()
    monkeypatch.setattr(coaching_cli, "run_coaching_generation", generate)

    coaching_cli.main(
        [
            "regenerate-latest",
            "--user-id",
            "4",
            "--activity-count",
            "3",
            "--week-count",
            "2",
            "--month-count",
            "1",
        ]
    )

    repository.list_latest_activity_ids.assert_called_once_with(user_id=4, count=3)
    assert [
               call.kwargs for call in repository.enqueue_activity_note.call_args_list
           ] == [
               {"user_id": 4, "activity_id": activity_id, "regenerate": True}
               for activity_id in (15, 14, 13)
           ]
    assert [
               call.kwargs for call in repository.requeue_latest_periods.call_args_list
           ] == [
               {"user_id": 4, "period_type": "week", "count": 2},
               {"user_id": 4, "period_type": "month", "count": 1},
           ]
    session.commit.assert_called_once()
    generate.assert_not_called()
    output = capsys.readouterr().out
    assert "2 week" in output and "1 month" in output
    assert "existing text remains visible" in output


def test_regenerate_latest_defaults_to_five_activities_one_week_and_one_month(
        monkeypatch,
):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    repository = Mock(spec=CoachingRepository)
    repository.list_latest_activity_ids.return_value = []
    repository.requeue_latest_periods.return_value = 0
    monkeypatch.setattr(coaching_cli, "SessionLocal", Mock(return_value=context))
    monkeypatch.setattr(
        coaching_cli, "CoachingRepository", Mock(return_value=repository)
    )

    coaching_cli.main(["regenerate-latest", "--user-id", "4"])

    repository.list_latest_activity_ids.assert_called_once_with(user_id=4, count=5)
    assert [
               call.kwargs for call in repository.requeue_latest_periods.call_args_list
           ] == [
               {"user_id": 4, "period_type": "week", "count": 1},
               {"user_id": 4, "period_type": "month", "count": 1},
           ]
    session.commit.assert_called_once()


def test_period_only_regeneration_does_not_select_activities(monkeypatch):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    repository = Mock(spec=CoachingRepository)
    repository.requeue_latest_periods.side_effect = [1, 1]
    monkeypatch.setattr(coaching_cli, "SessionLocal", Mock(return_value=context))
    monkeypatch.setattr(
        coaching_cli, "CoachingRepository", Mock(return_value=repository)
    )

    coaching_cli.main(
        [
            "regenerate-latest",
            "--user-id",
            "4",
            "--activity-count",
            "0",
        ]
    )

    repository.list_latest_activity_ids.assert_not_called()
    repository.enqueue_activity_note.assert_not_called()
    session.commit.assert_called_once()


def test_regeneration_error_does_not_commit_a_partial_batch(monkeypatch):
    session = Mock(spec=Session)
    context = MagicMock()
    context.__enter__.return_value = session
    repository = Mock(spec=CoachingRepository)
    repository.list_latest_activity_ids.return_value = [15]
    repository.requeue_latest_periods.side_effect = RuntimeError("Storage unavailable")
    monkeypatch.setattr(coaching_cli, "SessionLocal", Mock(return_value=context))
    monkeypatch.setattr(
        coaching_cli, "CoachingRepository", Mock(return_value=repository)
    )

    with pytest.raises(RuntimeError, match="Storage unavailable"):
        coaching_cli.main(["regenerate-latest", "--user-id", "4"])

    repository.enqueue_activity_note.assert_called_once_with(
        user_id=4,
        activity_id=15,
        regenerate=True,
    )
    session.commit.assert_not_called()
    assert context.__exit__.call_args.args[0] is RuntimeError


@pytest.mark.parametrize(
    "counts",
    [
        (-1, 3, 3),
        (101, 3, 3),
        (7, -1, 3),
        (7, 101, 3),
        (7, 3, -1),
        (7, 3, 101),
        (0, 0, 0),
    ],
)
def test_invalid_regeneration_bounds_do_not_touch_storage(monkeypatch, capsys, counts):
    session_factory = Mock()
    monkeypatch.setattr(coaching_cli, "SessionLocal", session_factory)
    with pytest.raises(SystemExit) as error:
        coaching_cli.main(
            [
                "regenerate-latest",
                "--user-id",
                "4",
                "--activity-count",
                str(counts[0]),
                "--week-count",
                str(counts[1]),
                "--month-count",
                str(counts[2]),
            ]
        )
    assert error.value.code == 2
    assert "Counts must be between 0 and 100" in capsys.readouterr().err
    session_factory.assert_not_called()
