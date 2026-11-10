from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.application.auth.current_user import CurrentUserService
from app.domain.schemas.user import CurrentUserResponse
from app.infrastructure.db.models.training_plan import (
    TrainingPlanDay,
    TrainingPlanRequest,
)
from app.infrastructure.db.models.user import User
from app.main import app


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
    client, db_session, monkeypatch
):
    monkeypatch.setattr(
        "app.application.read_models.training_plans.datetime",
        SimpleNamespace(now=lambda _: datetime(2026, 11, 10, tzinfo=UTC)),
    )
    session = db_session
    session.add_all(
        [User(id=i, display_name=f"Runner {i}", is_active=True) for i in (1, 2)]
    )
    session.flush()
    for i in (1, 2):
        request = TrainingPlanRequest(
            user_id=i,
            source_key="manual:first",
            status="ready",
            timezone="Europe/Prague",
            target_start=date(2026, 11, 30),
        )
        session.add(request)
        session.flush()
        session.add(
            TrainingPlanDay(
                user_id=i,
                request_id=request.id,
                planned_date=date(2026, 12, 1),
                kind="run",
                focus="easy",
                distance_meters=10000,
                pace_seconds_per_km=330,
                heart_rate_bpm=145,
                rationale=f"Endurance for athlete {i}",
                generated_at=datetime.now(UTC),
            )
        )
    session.add(
        TrainingPlanRequest(
            user_id=1,
            source_key="manual:second",
            status="pending",
            timezone="Europe/Prague",
        )
    )
    session.commit()
    app.dependency_overrides[CurrentUserService] = lambda: Athlete()
    response = client.get("/training-plans?date_from=2026-11-30&date_to=2026-12-06")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert len(data["items"]) == 1
    assert data["items"][0]["distance_km"] == 10
    assert data["items"][0]["pace_seconds_per_km"] == 330
    assert data["items"][0]["stale"] is True
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
    pending = (
        session.query(TrainingPlanRequest)
        .filter_by(user_id=1, source_key="manual:second")
        .one()
    )
    pending.context_json = {"weekly_objective": objective}
    session.commit()
    with_objective = client.get(
        "/training-plans?date_from=2026-11-30&date_to=2026-12-06"
    ).json()
    assert with_objective["weekly_objective"] == objective
    assert session.query(TrainingPlanRequest).count() == 3
    assert (
        client.get("/training-plans?date_from=2026-11-01&date_to=2026-11-30").json()[
            "items"
        ]
        == []
    )
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
