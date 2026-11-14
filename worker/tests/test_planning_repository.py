"""Planning adapter behavior with a mocked SQLAlchemy session and no database."""

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import and_
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Insert
from test_planning_policy import context, payload

from app.models import Activity, TrainingPlanRequest
from app.services.planning.repository import PlanningRepository


def query_result(row=None, rows=()):
    query = Mock()
    for method in (
            "filter",
            "join",
            "outerjoin",
            "order_by",
            "with_for_update",
            "populate_existing",
    ):
        getattr(query, method).return_value = query
    query.first.return_value = query.one.return_value = row
    query.all.return_value = list(rows)
    return query


def request_row(**updates):
    values = dict(
        id=1,
        user_id=1,
        status="generating",
        timezone="Europe/Prague",
        source_key="manual:first",
        lease_token="lease",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        attempt_count=0,
        context_json=None,
        last_error=None,
    )
    return TrainingPlanRequest(**dict(values, **updates))


def request_data(row):
    return dict(
        id=row.id,
        user_id=row.user_id,
        lease_token=row.lease_token,
        timezone=row.timezone,
        context=row.context_json,
        attempt_count=row.attempt_count,
    )


@pytest.fixture
def storage():
    session = Mock(spec=Session)
    session.scalar.return_value = None
    row = request_row()
    query = query_result(row)
    session.query.return_value = query
    return session, row, query, PlanningRepository(session)


def inserts(session, table):
    return [
        call.args[0]
        for call in session.execute.call_args_list
        if isinstance(call.args[0], Insert) and call.args[0].table.name == table
    ]


def test_sync_enqueue_reuses_its_idempotency_key_and_manual_requests_are_distinct(
        storage,
):
    session, _, _, repo = storage
    session.scalar.side_effect = [1, 1, 2, 3]
    assert repo.enqueue(user_id=1, sync_job_id=5, timezone="Europe/Prague") == 1
    assert repo.enqueue(user_id=1, sync_job_id=5, timezone="Europe/Prague") == 1
    repo.enqueue(user_id=1, timezone="Europe/Prague")
    repo.enqueue(user_id=1, timezone="Europe/Prague")
    statements = inserts(session, "training_plan_requests")
    keys = [statement.compile().params["source_key"] for statement in statements]
    assert keys[:2] == ["sync:5", "sync:5"]
    assert keys[2].startswith("manual:") and keys[2] != keys[3]
    assert "ON CONFLICT (user_id, source_key) DO NOTHING" in str(statements[0])
    session.commit.assert_not_called()  # The importing transaction owns this commit.


def test_claim_requires_active_athlete_completed_sync_and_current_lease(storage):
    session, row, query, repo = storage
    result = repo.claim(user_id=1)
    assert row.status == "generating"
    assert row.lease_expires_at > datetime.now(UTC)
    old_token = result["lease_token"]
    row.lease_token = "a replacement worker's token"
    assert result["lease_token"] == old_token
    predicates = [value for call in query.filter.call_args_list for value in call.args]
    sql = str(
        and_(*predicates).compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "users.is_active IS true" in sql
    assert "training_plan_requests.user_id = 1" in sql
    assert (
            "sync_jobs.status IN ('queued', 'running')" in sql
            and "sync_jobs.status = 'completed'" in sql
    )
    assert (
            "training_plan_requests.status = 'pending'" in sql
            and "lease_expires_at <=" in sql
    )
    session.commit.assert_called_once()


def test_empty_queue_makes_no_request(storage):
    session, _, query, repo = storage
    query.first.return_value = None
    assert repo.claim(user_id=1) is None
    assert not inserts(session, "training_plan_days")


@pytest.mark.parametrize("reason", ["expired", "replaced_lease", "newer_request"])
def test_stale_request_cannot_publish_targets(storage, reason):
    session, row, _, repo = storage
    request = request_data(row)
    if reason == "expired":
        row.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif reason == "replaced_lease":
        row.lease_token = "new lease"
    else:
        session.scalar.return_value = 2
    assert not repo.publish(
        request, payload()["days"], model="test", today=date(2026, 11, 10)
    )
    assert not inserts(session, "training_plan_days")
    if reason == "newer_request":
        assert row.status == "superseded"


def test_publication_defers_when_an_import_started_during_the_model_call(storage):
    session, row, _, repo = storage
    session.scalar.side_effect = [None, 9]
    assert not repo.publish(
        request_data(row), payload()["days"], model="test", today=date(2026, 11, 10)
    )
    assert row.status == "pending" and row.lease_token is None
    assert not inserts(session, "training_plan_days")


def test_publication_only_replaces_future_targets_and_commits_together(storage):
    session, row, _, repo = storage
    assert repo.publish(
        request_data(row), payload()["days"], model="new", today=date(2026, 11, 12)
    )
    values = [
        statement.compile().params
        for statement in inserts(session, "training_plan_days")
    ]
    assert len(values) == 5
    assert all(value["planned_date"] > date(2026, 11, 12) for value in values)
    assert all(value["user_id"] == 1 and value["request_id"] == 1 for value in values)
    assert row.status == "ready" and row.model == "new" and row.lease_token is None
    session.commit.assert_called_once()


def test_context_publication_retains_requested_dates_and_source_fingerprint(storage):
    session, row, _, repo = storage
    assert repo.save_context(request_data(row), context())
    assert row.context_json == context()
    assert len(row.source_hash) == 64
    assert row.target_start == date.fromisoformat(context()["dates"][0])
    session.commit.assert_called_once()


def test_retry_releases_lease_and_schedules_backoff(storage):
    _, row, _, repo = storage
    before = datetime.now(UTC)
    repo.finish(
        request_data(row),
        status="pending",
        error="Temporary error",
        delay=300,
        attempts=2,
    )
    assert row.lease_token is None and row.lease_expires_at is None
    assert row.next_attempt_at >= before + timedelta(seconds=300)
    assert row.attempt_count == 2 and row.last_error == "Temporary error"


@pytest.mark.parametrize(
    "today", [date(2026, 3, 28), date(2026, 10, 24), date(2026, 12, 31)]
)
def test_planning_context_uses_calendar_dates_across_dst_and_year_boundaries(
        storage, today
):
    session, row, _, repo = storage
    activities = []
    for i in range(3):
        start = datetime.combine(
            today - timedelta(days=2 * i), datetime.min.time(), tzinfo=UTC
        )
        activities.append(
            (
                Activity(
                    id=i + 1,
                    user_id=1,
                    sport_type="Run",
                    start_date_local=start,
                    start_date_utc=start,
                    distance_meters=10000,
                    moving_time_seconds=3300,
                    average_pace_seconds_per_km=330,
                    average_heartrate_bpm=140,
                ),
                None,
            )
        )
    session.query.side_effect = [
        query_result(rows=activities),
        query_result(),
        query_result(),
        query_result(),
    ]
    result = repo.build_context(request_data(row), today)
    assert result["dates"] == [
        (today + timedelta(days=i)).isoformat() for i in range(1, 8)
    ]
    assert result["timezone"] == "Europe/Prague" and len(result["activities"]) == 3


def test_legacy_context_upgrades_without_moving_dates_and_continues_ready_objective(
        storage,
):
    from test_planning_objective import THRESHOLDS, TODAY, established_training

    from app.services.planning.policy import PROMPT_VERSION

    _, row, query, repo = storage
    legacy = {
        "today": str(TODAY),
        "dates": [str(TODAY + timedelta(days=i)) for i in range(1, 8)],
        "activities": established_training(),
        "thresholds": THRESHOLDS,
        "previous_plans": [],
        "bounds": {},
    }
    query.first.return_value = None
    request = dict(request_data(row), context=legacy)
    upgraded = repo.build_context(request, TODAY)
    assert upgraded["policy_version"] == PROMPT_VERSION
    assert (
            upgraded["dates"] == legacy["dates"]
            and upgraded["weekly_objective"]["mode"] == "build"
    )
    query.first.return_value = SimpleNamespace(context_json=upgraded)
    continued = repo.build_context(
        dict(request, context=dict(legacy, today=str(TODAY + timedelta(days=1)))),
        TODAY + timedelta(days=1),
    )
    assert continued["weekly_objective"]["continued"]
    assert (
        continued["weekly_objective"]["review_date"]
        == upgraded["weekly_objective"]["review_date"]
    )
