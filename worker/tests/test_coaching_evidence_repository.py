"""Exercise reusable evidence against an isolated PostgreSQL schema."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, text
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Activity,
    ActivityCoachingEvidence,
    ActivitySplits,
    ActivityStream,
    Base,
    User,
    UserThresholdProfile,
)
from app.repositories import CoachingRepository


@pytest.fixture
def evidence_session():
    schema = "pytest_coaching_" + uuid4().hex
    engine = create_engine(
        settings.database_url, connect_args={"options": f"-csearch_path={schema}"}
    )
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        Base.metadata.create_all(connection)
    with Session(engine) as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.add(User(id=1, display_name="Runner", is_active=True))
        session.flush()
        session.add(
            Activity(
                id=1,
                user_id=1,
                source_activity_id=1,
                source_provider="garmin",
                name="Steady run",
                sport_type="Run",
                start_date_local=datetime(2026, 11, 12, tzinfo=UTC),
                start_date_utc=datetime(2026, 11, 12, tzinfo=UTC),
                distance_meters=Decimal("300"),
                moving_time_seconds=30,
                total_elevation_gain_meters=0,
            )
        )
        session.add(
            ActivityStream(
                activity_id=1,
                time_stream={"data": [0, 10, 20, 30]},
                distance_stream={"data": [0, 100, 200, 300]},
                heartrate_stream={"data": [130, 139, 140, 165]},
            )
        )
        session.add(
            UserThresholdProfile(
                user_id=1,
                effective_from=date(2026, 10, 1),
                aet_heart_rate_bpm=140,
                ant_heart_rate_bpm=165,
                aet_pace_min_per_km=5.5,
                ant_pace_min_per_km=4.5,
            )
        )
        session.flush()
        session.add(ActivitySplits(activity_id=1, status="unavailable", laps=[]))
        session.commit()
        yield session
        session.rollback()
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(delete(table))
        session.commit()
    with engine.begin() as connection:
        connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    engine.dispose()


def test_persisted_facts_reused_and_invalidated_for_changed_streams_and_dated_thresholds(
    evidence_session,
):
    session = evidence_session
    repo = CoachingRepository(session)
    activities = [session.get(Activity, 1)]
    first = repo.activity_evidence_batch(user_id=1, activities=activities)[1]
    session.commit()
    assert first["hr_bands"]["bands"]["above_ant"]["time_s"] == 10
    cached = session.get(ActivityCoachingEvidence, 1)
    original_hash = cached.source_hash
    assert repo.activity_evidence_batch(user_id=1, activities=activities)[1] == first
    assert session.query(ActivityCoachingEvidence).count() == 1
    assert cached.source_hash == original_hash
    session.add(
        UserThresholdProfile(
            user_id=1,
            effective_from=date(2026, 11, 13),
            aet_heart_rate_bpm=150,
            ant_heart_rate_bpm=170,
            aet_pace_min_per_km=5.5,
            ant_pace_min_per_km=4.5,
        )
    )
    session.commit()
    assert repo.activity_evidence_batch(user_id=1, activities=activities)[1] == first
    # A future snapshot must never change historical evidence.
    assert cached.source_hash == original_hash
    row = session.query(ActivityStream).filter_by(activity_id=1).one()
    row.heartrate_stream = {"data": [130, 130, 130, 130]}
    session.flush()
    changed = repo.activity_evidence_batch(user_id=1, activities=activities)[1]
    assert changed["hr_bands"]["bands"]["below_aet"]["time_s"] == 30
    assert cached.source_hash != original_hash
    threshold = (
        session.query(UserThresholdProfile)
        .filter_by(effective_from=date(2026, 10, 1))
        .one()
    )
    threshold.aet_heart_rate_bpm = 125
    session.flush()
    changed = repo.activity_evidence_batch(user_id=1, activities=activities)[1]
    assert changed["hr_bands"]["bands"]["between_aet_ant"]["time_s"] == 30


def test_local_generation_pipeline_stores_metrics_and_revisits_dependents(
    evidence_session,
):
    from app.models import ActivityCoachingNote, PeriodCoachingSummary
    from app.services.coaching.generator import CoachingGenerator
    from app.services.coaching.llm_client import LlmCompletion

    session = evidence_session
    session.add(
        ActivityCoachingNote(
            activity_id=1, user_id=1, status="ready", summary="Controlled effort."
        )
    )
    session.commit()

    class OfflineModel:
        calls = 0

        def complete_json(self, *, system_prompt, user_prompt):
            import json

            self.calls += 1
            context = json.loads(user_prompt.split("\n", 1)[1])
            assert (
                context["hr_bands_by_sport"]["Run"]["bands"]["above_ant"]["time_s"]
                == 10
            )
            assert '"laps":' not in user_prompt
            return LlmCompletion(
                payload={
                    "summary": "Offline validation only.",
                    "recommendation": "Recover.",
                },
                model="offline-test",
            )

    model = OfflineModel()
    generator = CoachingGenerator(
        repository=CoachingRepository(session),
        llm_client=model,
        batch_size=2,
        today=lambda: date(2026, 11, 13),
    )
    assert generator.run(user_id=1).period_summaries_generated == 2
    periods = session.query(PeriodCoachingSummary).all()
    assert {row.period_type for row in periods} == {"week", "month"}
    assert all(
        row.metrics["hr_bands_by_sport"]["Run"]["bands"]["below_aet"]["distance_m"]
        == 100
        for row in periods
    )
    assert generator.run(user_id=1).period_summaries_generated == 0
    # An older review is kept on prompt rollout unless explicitly queued.
    for row in periods:
        row.prompt_version = "2"
        row.source_hash = "legacy"
    session.commit()
    assert generator.run(user_id=1).period_summaries_generated == 0
    repo = CoachingRepository(session)
    for row in periods:
        repo.mark_period_pending(row)
    assert generator.run(user_id=1).period_summaries_generated == 2
    assert model.calls == 4
    session.query(ActivityStream).filter_by(activity_id=1).one().heartrate_stream = {
        "data": [130, 150, 140, 165]
    }
    session.commit()
    assert generator.run(user_id=1).period_summaries_generated == 2
    assert model.calls == 6
    assert all(
        row.metrics["hr_bands_by_sport"]["Run"]["bands"]["below_aet"]["time_s"] == 0
        for row in periods
    )


def test_cli_bounds_regeneration_and_keeps_old_text(
    evidence_session, monkeypatch, capsys
):
    from contextlib import contextmanager
    from app import coaching_cli
    from app.models import PeriodCoachingSummary

    session = evidence_session
    session.add_all(
        [
            PeriodCoachingSummary(
                user_id=1,
                period_type=kind,
                period_start=day,
                status="ready",
                summary="Existing review.",
                recommendation="Existing advice.",
            )
            for kind, day in [("week", date(2026, 11, 9)), ("month", date(2026, 11, 1))]
        ]
    )
    session.commit()

    @contextmanager
    def local_session():
        yield session

    monkeypatch.setattr(coaching_cli, "SessionLocal", local_session)
    monkeypatch.setattr(coaching_cli, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        coaching_cli,
        "run_coaching_generation",
        lambda **kwargs: pytest.fail("No AI calls from queue preparation"),
    )
    coaching_cli.main(
        [
            "regenerate-periods",
            "--user-id",
            "1",
            "--date-from",
            "2026-11-01",
            "--date-to",
            "2026-11-30",
            "--period-type",
            "week",
            "--limit",
            "1",
        ]
    )
    rows = (
        session.query(PeriodCoachingSummary)
        .order_by(PeriodCoachingSummary.period_type)
        .all()
    )
    assert [(row.period_type, row.status) for row in rows] == [
        ("month", "ready"),
        ("week", "pending"),
    ]
    assert all(row.summary == "Existing review." for row in rows)
    coaching_cli.main(
        ["prepare-evidence", "--user-id", "1", "--after-id", "0", "--limit", "1"]
    )
    assert "Resume with --after-id 1" in capsys.readouterr().out
    assert session.query(ActivityCoachingEvidence).count() == 1
