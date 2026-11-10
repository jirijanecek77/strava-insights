from unittest.mock import Mock

from app import coaching_cli
from app.models import TrainingPlanRequest
from app.services.planning.generator import PlanningRunStats
from test_planning_repository import planning_engine, planning_session


def test_manual_cli_requests_a_fresh_plan_without_new_activity(
    planning_session, monkeypatch, capsys
):
    session = planning_session
    monkeypatch.setattr(coaching_cli, "configure_logging", lambda **_: None)

    # Let the real CLI persist requests while keeping the fixture's test session open.
    class SessionContext:
        def __enter__(self):
            return session

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(coaching_cli, "SessionLocal", SessionContext)
    generate = Mock(return_value=PlanningRunStats())
    monkeypatch.setattr(coaching_cli, "run_planning_generation", generate)
    coaching_cli.main(["replan", "--user-id", "1"])
    coaching_cli.main(["replan", "--user-id", "1"])
    assert session.query(TrainingPlanRequest).count() == 2
    assert generate.call_count == 2
    assert "Queued for background processing" in capsys.readouterr().out


def test_cli_explains_the_weekly_objective(capsys):
    from types import SimpleNamespace
    from test_planning_objective import TODAY, THRESHOLDS, established_training
    from app.services.planning.policy import training_bounds

    objective = training_bounds(established_training(), THRESHOLDS, TODAY)[
        "weekly_objective"
    ]
    coaching_cli._print_objective(
        SimpleNamespace(context_json={"weekly_objective": objective})
    )
    output = capsys.readouterr().out
    assert "Objective: build" in output
    assert "Review on" in output
    assert objective["reason"] in output
