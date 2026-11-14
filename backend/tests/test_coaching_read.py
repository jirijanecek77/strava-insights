from datetime import UTC, date, datetime
from unittest.mock import Mock

from app.application.auth.current_user import CurrentUserService
from app.application.coaching import read
from app.infrastructure.db.models.activity import Activity
from app.infrastructure.db.models.coaching import (
    ActivityCoachingNote,
    PeriodCoachingSummary,
)
from app.main import app
from tests.read_mocks import mock_activity_repositories
from tests.test_read_endpoint_integration import CurrentUserServiceStub


def test_activity_detail_includes_stored_coaching_note(client, monkeypatch):
    activities = [
        Activity(
            id=i,
            user_id=user,
            source_activity_id=i,
            source_provider="garmin",
            name="Run",
            sport_type="Run",
            distance_meters=10000,
            moving_time_seconds=3000,
            start_date_utc=datetime(2026, 9, 29, tzinfo=UTC),
            start_date_local=datetime(2026, 9, 29, tzinfo=UTC),
        )
        for i, user in ((21, 1), (22, 1), (23, 2))
    ]
    repositories = mock_activity_repositories(monkeypatch, activities)
    notes = {
        21: ActivityCoachingNote(
            activity_id=21,
            user_id=1,
            status="ready",
            description="Steady aerobic run.",
            summary="Easy 10 km.",
            recommendation="Recover tomorrow.",
            model="test",
        ),
        22: ActivityCoachingNote(activity_id=22, user_id=1, status="pending"),
    }
    repositories.coaching.get_activity_note.side_effect = (
        lambda user, activity: notes.get(activity)
    )
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    ready = client.get("/activities/21").json()["coaching"]
    assert ready["description"] == "Steady aerobic run."
    assert ready["summary"] == "Easy 10 km."
    assert ready["recommendation"] == "Recover tomorrow."
    assert ready["model"] == "test"
    pending = client.get("/activities/22").json()["coaching"]
    assert pending["status"] == "pending" and pending["description"] is None
    assert client.get("/activities/23").status_code == 404
    assert all(
        call.args[0] == 1
        for call in repositories.coaching.get_activity_note.call_args_list
    )


def test_period_coaching_lists_overlapping_periods_for_current_user(
        client, monkeypatch
):
    rows = [
        PeriodCoachingSummary(
            user_id=1,
            period_type="week",
            period_start=date(2026, 9, 28),
            status="ready",
            summary="Solid week.",
            recommendation="Add one tempo session.",
            is_final=True,
            metrics={
                "hr_bands_by_sport": {
                    "Run": {
                        "bands": {"below_aet": {"time_s": 1200, "distance_m": 3000}}
                    }
                }
            },
        ),
        PeriodCoachingSummary(
            user_id=1,
            period_type="month",
            period_start=date(2026, 9, 1),
            status="pending",
            is_final=False,
        ),
        PeriodCoachingSummary(
            user_id=1,
            period_type="month",
            period_start=date(2026, 8, 1),
            status="ready",
            is_final=True,
        ),
    ]
    repository = Mock(spec=read.CoachingRepository)
    repository.list_period_summaries.return_value = sorted(
        rows, key=lambda row: (row.period_type, row.period_start)
    )
    monkeypatch.setattr(read, "CoachingRepository", Mock(return_value=repository))
    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    response = client.get("/coaching/periods?date_from=2026-09-01&date_to=2026-09-30")
    assert response.status_code == 200
    month, week = response.json()["items"]
    assert month["status"] == "pending" and month["metrics"] is None
    assert month["period_end"] == "2026-09-30"
    assert week["period_start"] == "2026-09-28" and week["period_end"] == "2026-10-04"
    assert week["is_final"] and week["summary"] == "Solid week."
    assert (
            week["metrics"]["hr_bands_by_sport"]["Run"]["bands"]["below_aet"]["distance_m"]
            == 3000
    )
    repository.list_period_summaries.assert_called_once_with(
        1, date_from=date(2026, 8, 26), date_to=date(2026, 9, 30)
    )
    october = client.get(
        "/coaching/periods?date_from=2026-10-01&date_to=2026-10-31"
    ).json()["items"]
    assert [(row["period_type"], row["period_start"]) for row in october] == [
        ("week", "2026-09-28")
    ]
    assert (
            client.get(
                "/coaching/periods?date_from=2026-10-31&date_to=2026-10-01"
            ).status_code
            == 422
    )
