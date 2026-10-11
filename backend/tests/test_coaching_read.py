from app.application.auth.current_user import CurrentUserService
from app.infrastructure.db.models.activity import Activity
from app.infrastructure.db.models.coaching import (
    ActivityCoachingNote,
    PeriodCoachingSummary,
)
from app.infrastructure.db.models.user import User
from app.main import app
from datetime import UTC, date, datetime
from decimal import Decimal

from tests.test_read_endpoint_integration import CurrentUserServiceStub


def _seed(db_session) -> None:
    for user_id in (1, 2):
        db_session.add(
            User(
                id=user_id,
                external_user_id=f"ext-{user_id}",
                source_provider="garmin",
                display_name=f"Athlete {user_id}",
                profile_picture_url=None,
                is_active=True,
            )
        )
    db_session.flush()
    db_session.add_all(
        [
            Activity(
                id=activity_id,
                user_id=user_id,
                source_activity_id=3000 + activity_id,
                source_provider="garmin",
                name="Morning Run",
                sport_type="Run",
                start_date_utc=datetime(2026, 9, 29, 6, tzinfo=UTC),
                start_date_local=datetime(2026, 9, 29, 8, tzinfo=UTC),
                distance_meters=Decimal("10000"),
                moving_time_seconds=3000,
            )
            for activity_id, user_id in ((21, 1), (22, 1), (23, 2))
        ]
    )
    db_session.flush()
    db_session.add_all(
        [
            ActivityCoachingNote(
                activity_id=21,
                user_id=1,
                status="ready",
                description="Steady aerobic run.",
                summary="Easy 10 km.",
                recommendation="Recover tomorrow.",
                model="gemini-test",
                generated_at=datetime(2026, 9, 29, 9, tzinfo=UTC),
            ),
            ActivityCoachingNote(activity_id=22, user_id=1, status="pending"),
            ActivityCoachingNote(
                activity_id=23,
                user_id=2,
                status="ready",
                description="Other athlete.",
                summary="Other athlete.",
            ),
            PeriodCoachingSummary(
                user_id=1,
                period_type="week",
                period_start=date(2026, 9, 28),
                status="ready",
                summary="Solid week.",
                recommendation="Add one tempo session.",
                is_final=True,
            ),
            PeriodCoachingSummary(
                user_id=1,
                period_type="month",
                period_start=date(2026, 9, 1),
                status="pending",
            ),
            PeriodCoachingSummary(
                user_id=1,
                period_type="month",
                period_start=date(2026, 8, 1),
                status="ready",
                summary="Outside the requested range.",
            ),
            PeriodCoachingSummary(
                user_id=2,
                period_type="week",
                period_start=date(2026, 9, 28),
                status="ready",
                summary="Other athlete.",
            ),
        ]
    )
    db_session.commit()


def test_activity_detail_includes_stored_coaching_note(client, db_session) -> None:
    _seed(db_session)
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    try:
        ready = client.get("/activities/21").json()["coaching"]
        assert ready["status"] == "ready"
        assert ready["description"] == "Steady aerobic run."
        assert ready["summary"] == "Easy 10 km."
        assert ready["recommendation"] == "Recover tomorrow."
        assert ready["model"] == "gemini-test"

        pending = client.get("/activities/22").json()["coaching"]
        assert pending["status"] == "pending"
        assert pending["description"] is None
    finally:
        app.dependency_overrides.clear()


def test_period_coaching_lists_overlapping_periods_for_current_user(client, db_session) -> None:
    _seed(db_session)
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    try:
        response = client.get(
            "/coaching/periods", params={"date_from": "2026-09-01", "date_to": "2026-09-30"}
        )
        assert response.status_code == 200
        items = response.json()["items"]
        assert [(item["period_type"], item["period_start"]) for item in items] == [
            ("month", "2026-09-01"),
            ("week", "2026-09-28"),
        ]
        month, week = items
        assert month["status"] == "pending"
        assert month["period_end"] == "2026-09-30"
        assert week["summary"] == "Solid week."
        assert week["period_end"] == "2026-10-04"
        assert week["is_final"] is True

        october = client.get(
            "/coaching/periods", params={"date_from": "2026-10-01", "date_to": "2026-10-31"}
        ).json()["items"]
        assert [(item["period_type"], item["period_start"]) for item in october] == [
            ("week", "2026-09-28")
        ]

        invalid = client.get(
            "/coaching/periods", params={"date_from": "2026-10-31", "date_to": "2026-10-01"}
        )
        assert invalid.status_code == 422
    finally:
        app.dependency_overrides.clear()
