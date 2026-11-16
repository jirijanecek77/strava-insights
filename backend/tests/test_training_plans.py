from app.application.auth.current_user import CurrentUserService
from app.domain.schemas.user import CurrentUserResponse
from app.infrastructure.db.models.training_plan import (
    TrainingPlanDay,
    TrainingPlanRequest,
)
from app.infrastructure.repositories.training_plan_repository import TrainingPlanRepository
from app.main import app
from datetime import UTC, date, datetime
from sqlalchemy import and_
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from types import SimpleNamespace
from unittest.mock import Mock


class Athlete:
    def __init__(self, user_id=1):
        self.user_id = user_id

    def get_current_user(self, request):
        return (
            CurrentUserResponse(id=self.user_id, display_name="Runner")
            if self.user_id
            else None
        )


def test_training_plan_reads_are_scoped_and_preserve_old_targets_while_pending(
        client, monkeypatch
):
    monkeypatch.setattr(
        "app.application.read_models.training_plans.datetime",
        SimpleNamespace(now=lambda _: datetime(2026, 11, 10, tzinfo=UTC)),
    )
    from app.application.read_models import training_plans

    repository = Mock(spec=training_plans.TrainingPlanRepository)
    request = TrainingPlanRequest(
        id=2, user_id=1, status="pending", timezone="Europe/Prague", context_json=None
    )
    day = TrainingPlanDay(
        user_id=1,
        request_id=1,
        planned_date=date(2026, 12, 1),
        kind="run",
        focus="easy",
        distance_meters=10000,
        pace_seconds_per_km=330,
        heart_rate_bpm=145,
        rationale="Endurance for athlete 1",
        generated_at=datetime.now(UTC),
    )
    repository.latest_request.return_value = request
    repository.completed_activity_dates.return_value = {date(2026, 12, 1)}
    repository.list_days.side_effect = lambda user_id, *, date_from, date_to: (
        [day] if date_from <= day.planned_date <= date_to else []
    )
    monkeypatch.setattr(
        training_plans, "TrainingPlanRepository", Mock(return_value=repository)
    )
    app.dependency_overrides[CurrentUserService] = lambda: Athlete()
    response = client.get("/training-plans?date_from=2026-11-30&date_to=2026-12-06")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert len(data["items"]) == 1
    assert data["items"][0]["distance_km"] == 10
    assert data["items"][0]["pace_seconds_per_km"] == 330
    assert data["items"][0]["stale"] is True
    assert data["items"][0]["has_completed_activity"] is True
    repository.completed_activity_dates.assert_called_once_with(
        1, date_from=date(2026, 11, 30), date_to=date(2026, 12, 6)
    )
    assert data["items"][0]["rationale"] == "Endurance for athlete 1"
    assert data["weekly_objective"] is None  # Legacy requests remain readable.
    objective = {
        "mode": "maintain",
        "block_start": "2026-11-30",
        "review_date": "2026-12-07",
        "reason": "Consolidate recent training volume.",
        "evidence": ["Latest week: 60 km."],
        "continued": False,
        "target_distance_km": 57,
        "distance_min_km": 54,
        "distance_max_km": 60,
        "target_running_days": 5,
        "long_run_min_km": 18,
        "long_run_max_km": 21,
    }
    request.context_json = {"weekly_objective": objective}
    repository.completed_activity_dates.return_value = set()
    with_objective = client.get(
        "/training-plans?date_from=2026-11-30&date_to=2026-12-06"
    ).json()
    assert with_objective["weekly_objective"] == objective
    assert with_objective["items"][0]["has_completed_activity"] is False
    assert all(
        call.args[0] == 1 for call in repository.completed_activity_dates.call_args_list
    )
    assert all(call.args[0] == 1 for call in repository.list_days.call_args_list)
    assert (
        client.get("/training-plans?date_from=2026-11-01&date_to=2026-11-30").json()[
            "items"
        ]
        == []
    )
    assert repository.completed_activity_dates.call_count == 2
    assert (
        client.get(
            "/training-plans?date_from=2026-12-02&date_to=2026-12-01"
        ).status_code
        == 422
    )
    app.dependency_overrides[CurrentUserService] = lambda: Athlete(None)
    assert (
        client.get(
            "/training-plans?date_from=2026-11-01&date_to=2026-12-01"
        ).status_code
        == 401
    )


def test_completed_activity_dates_include_all_sports_and_are_scoped_to_user_and_range():
    session = Mock(spec=Session)
    query = session.query.return_value
    query.filter.return_value = query
    query.distinct.return_value = query
    query.all.return_value = [(date(2026, 12, 1),), (date(2026, 12, 2),)]

    dates = TrainingPlanRepository(session).completed_activity_dates(
        7, date_from=date(2026, 11, 30), date_to=date(2026, 12, 6)
    )

    assert dates == {date(2026, 12, 1), date(2026, 12, 2)}
    condition = and_(*query.filter.call_args.args)
    sql = str(
        condition.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "activities.user_id = 7" in sql
    assert "CAST(activities.start_date_local AS DATE) >= '2026-11-30'" in sql
    assert "CAST(activities.start_date_local AS DATE) <= '2026-12-06'" in sql
    assert "sport_type" not in sql
