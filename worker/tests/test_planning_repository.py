"""Exercise durable queue and publication against an isolated PostgreSQL test schema."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Base, SyncJob, TrainingPlanDay, TrainingPlanRequest, User
from app.services.planning.repository import PlanningRepository
from test_planning_policy import context, payload


@pytest.fixture(scope="module")
def planning_engine():
    engine = create_engine(
        settings.database_url, connect_args={"options": "-csearch_path=pytest_planning"}
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS pytest_planning"))
        Base.metadata.create_all(conn)
    yield engine
    engine.dispose()


@pytest.fixture
def planning_session(planning_engine):
    with Session(planning_engine) as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.add_all(
            [
                User(id=1, display_name="Runner", is_active=True),
                User(id=2, display_name="Other", is_active=True),
            ]
        )
        session.commit()
        yield session
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.commit()


def enqueue(session, sync=None):
    repo = PlanningRepository(session)
    request_id = repo.enqueue(user_id=1, sync_job_id=sync, timezone="Europe/Prague")
    session.commit()
    return repo, request_id


def test_import_batch_is_idempotent_and_waits_for_success(planning_session):
    session = planning_session
    session.add(SyncJob(id=1, user_id=1, status="running", sync_type="full_import"))
    session.commit()
    repo, first = enqueue(session, sync=1)
    _, again = enqueue(session, sync=1)
    assert first == again
    assert repo.claim(user_id=1) is None
    session.get(SyncJob, 1).status = "failed"
    session.commit()
    assert repo.claim(user_id=1) is None
    session.get(SyncJob, 1).status = "completed"
    session.commit()
    assert repo.claim(user_id=1)["id"] == first
    assert repo.claim(user_id=1) is None


def test_latest_request_and_lease_token_prevent_stale_publication(planning_session):
    session = planning_session
    repo, first = enqueue(session)
    old = repo.claim(user_id=1)
    _, second = enqueue(session)
    assert (
        repo.publish(old, payload()["days"], model="test", today=date(2026, 11, 10))
        is False
    )
    assert session.query(TrainingPlanDay).count() == 0
    assert session.get(TrainingPlanRequest, first).status == "superseded"
    claimed = repo.claim(user_id=1)
    assert claimed["id"] == second
    session.get(TrainingPlanRequest, second).lease_expires_at = datetime.now(
        UTC
    ) - timedelta(seconds=1)
    session.commit()
    reclaimed = repo.claim(user_id=1)
    assert reclaimed["lease_token"] != claimed["lease_token"]
    assert not repo.save_context(claimed, context())
    assert repo.save_context(reclaimed, context())


def test_atomic_replacement_keeps_past_targets_and_other_users(planning_session):
    session = planning_session
    repo, first = enqueue(session)
    claimed = repo.claim(user_id=1)
    repo.save_context(claimed, context())
    assert repo.publish(
        claimed, payload()["days"], model="test", today=date(2026, 11, 10)
    )
    assert session.query(TrainingPlanDay).count() == 7
    _, second = enqueue(session)
    claimed2 = repo.claim(user_id=1)
    updated = payload()["days"]
    updated[3]["rationale"] = "Build endurance after recovery."
    repo.save_context(claimed2, context())
    assert repo.publish(claimed2, updated, model="new", today=date(2026, 11, 12))
    rows = session.query(TrainingPlanDay).order_by(TrainingPlanDay.planned_date).all()
    assert len(rows) == 7
    assert [d.request_id for d in rows[:2]] == [first, first]
    assert all(d.request_id == second for d in rows[2:])
    assert rows[3].rationale == updated[3]["rationale"]
    assert repo.claim(user_id=2) is None


def test_disabled_athlete_and_active_sync_cannot_generate(planning_session):
    session = planning_session
    repo, _ = enqueue(session)
    session.get(User, 1).is_active = False
    session.commit()
    assert repo.claim(user_id=1) is None
    session.get(User, 1).is_active = True
    session.add(SyncJob(user_id=1, status="queued", sync_type="incremental_sync"))
    session.commit()
    assert repo.claim(user_id=1) is None


def test_ready_or_failed_requests_never_regenerate_on_date_or_configuration_change(
    planning_session,
):
    session = planning_session
    repo, request_id = enqueue(session)
    claimed = repo.claim(user_id=1)
    repo.finish(claimed, status="failed", error="Invalid targets.", attempts=5)
    assert repo.claim(user_id=1) is None
    session.get(TrainingPlanRequest, request_id).status = "ready"
    session.commit()
    assert repo.claim(user_id=1) is None
    assert session.query(TrainingPlanRequest).count() == 1


@pytest.mark.parametrize("sport", ["Run", "Ride", "EBikeRide"])
def test_import_records_one_request_with_activity_and_backfills_never_replan(
    planning_session, monkeypatch, sport
):
    from unittest.mock import Mock
    from app.models import Activity
    from app.services.sync_import import FullImportService

    session = planning_session
    session.add(SyncJob(id=1, user_id=1, status="running", sync_type="full_import"))
    session.commit()
    garmin = Mock()
    garmin.connect.return_value.token_json.return_value = "{}"
    garmin.get_activities.return_value = [
        {
            "id": i,
            "type": sport,
            "name": "Session",
            "distance": 10000,
            "moving_time": 3300,
            "start_date": "2026-11-09T10:00:00+00:00",
        }
        for i in [51, 52]
    ]
    garmin.get_activity_stream.return_value = {
        "time": {"data": [0, 60]},
        "distance": {"data": [0, 180]},
    }
    service = FullImportService(session, garmin_client=garmin, token_cipher=Mock())
    monkeypatch.setattr(service, "_get_garmin_credentials", lambda _: "{}")
    monkeypatch.setattr(service, "_update_derived_data", lambda **_: (False, True))
    service.cache_invalidator = Mock()

    def persist_tokens(*_):
        # The real adapter commits token refreshes; a planning intent must already accompany every new activity.
        if session.query(Activity).count():
            assert session.query(TrainingPlanRequest).count() == 1
        session.commit()

    monkeypatch.setattr(service, "_persist_garmin_credentials", persist_tokens)
    service.run(sync_job_id=1, user_id=1)
    assert session.query(Activity).count() == 2
    assert session.query(TrainingPlanRequest).count() == 1
    assert session.get(SyncJob, 1).status == "completed"
    # Force existing-activity stream backfill on the next import; it must not create another plan request.
    session.add(SyncJob(id=2, user_id=1, status="running", sync_type="full_import"))
    session.commit()
    monkeypatch.setattr(
        service, "_existing_activity_needs_stream_backfill", lambda **_: True
    )
    service.run(sync_job_id=2, user_id=1)
    assert session.query(TrainingPlanRequest).count() == 1
    # A subsequent no-change import has the same behavior.
    session.add(SyncJob(id=3, user_id=1, status="running", sync_type="full_import"))
    session.commit()
    garmin.get_activities.return_value = []
    service.run(sync_job_id=3, user_id=1)
    assert session.query(TrainingPlanRequest).count() == 1


def test_later_successful_sync_releases_intent_from_partially_failed_import(
    planning_session,
):
    session = planning_session
    session.add(SyncJob(id=1, user_id=1, status="failed", sync_type="full_import"))
    session.commit()
    repo, request_id = enqueue(session, sync=1)
    assert repo.claim(user_id=1) is None
    session.add(
        SyncJob(
            id=2,
            user_id=1,
            status="completed",
            sync_type="incremental_sync",
            finished_at=datetime.now(UTC) + timedelta(seconds=1),
        )
    )
    session.commit()
    assert repo.claim(user_id=1)["id"] == request_id
    assert session.query(TrainingPlanRequest).count() == 1


@pytest.mark.parametrize(
    "today", [date(2026, 3, 28), date(2026, 10, 24), date(2026, 12, 31)]
)
def test_planning_window_uses_calendar_dates_across_dst_month_and_year_boundaries(
    planning_session, today
):
    from app.models import Activity

    session = planning_session
    for i in range(3):
        start = datetime.combine(
            today - timedelta(days=2 * i), datetime.min.time(), tzinfo=UTC
        )
        session.add(
            Activity(
                user_id=1,
                source_activity_id=600 + i,
                source_provider="garmin",
                name="Easy",
                sport_type="Run",
                start_date_utc=start,
                start_date_local=start,
                distance_meters=10000,
                moving_time_seconds=3300,
                average_pace_seconds_per_km=330,
                average_heartrate_bpm=140,
            )
        )
    session.commit()
    repo, _ = enqueue(session)
    request = repo.claim(user_id=1)
    ctx = repo.build_context(request, today)
    assert ctx["dates"] == [
        (today + timedelta(days=i)).isoformat() for i in range(1, 8)
    ]
    assert ctx["timezone"] == "Europe/Prague"
    assert len(ctx["activities"]) == 3


def test_queued_legacy_context_upgrades_in_place_and_ready_objective_continues(
    planning_session,
):
    from app.services.planning.policy import PROMPT_VERSION
    from test_planning_objective import TODAY, THRESHOLDS, established_training

    session = planning_session
    repo, first = enqueue(session)
    claimed = repo.claim(user_id=1)
    legacy = {
        "today": str(TODAY),
        "dates": [(TODAY + timedelta(days=i)).isoformat() for i in range(1, 8)],
        "activities": established_training(),
        "thresholds": THRESHOLDS,
        "previous_plans": [],
        "bounds": {},
    }
    claimed["context"] = legacy
    upgraded = repo.build_context(claimed, TODAY)
    assert upgraded["policy_version"] == PROMPT_VERSION
    assert upgraded["dates"] == legacy["dates"]
    assert upgraded["weekly_objective"]["mode"] == "build"
    repo.save_context(claimed, upgraded)
    session.get(TrainingPlanRequest, first).status = "ready"
    session.commit()
    _, second = enqueue(session)
    next_claim = repo.claim(user_id=1)
    next_claim["context"] = dict(legacy, today=str(TODAY + timedelta(days=1)))
    continued = repo.build_context(next_claim, TODAY + timedelta(days=1))
    assert continued["weekly_objective"]["continued"]
    assert (
        continued["weekly_objective"]["review_date"]
        == upgraded["weekly_objective"]["review_date"]
    )
    assert session.query(TrainingPlanRequest).count() == 2
