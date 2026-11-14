from unittest.mock import Mock

from app import coaching_cli
from app.services.planning.generator import PlanningRunStats


def test_manual_cli_requests_a_fresh_plan_without_new_activity(monkeypatch, capsys):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from sqlalchemy.orm import Session

    from app.models import User

    session = Mock(spec=Session)
    session.get.side_effect = lambda model, key: (
        SimpleNamespace(is_active=True)
        if model is User
        else SimpleNamespace(status="pending", last_error=None, context_json=None)
    )
    session_context = MagicMock()
    session_context.__enter__.return_value = session
    monkeypatch.setattr(
        coaching_cli, "SessionLocal", Mock(return_value=session_context)
    )
    repository = Mock()
    repository.enqueue.side_effect = [1, 2]
    monkeypatch.setattr(
        coaching_cli, "PlanningRepository", Mock(return_value=repository)
    )
    monkeypatch.setattr(coaching_cli, "configure_logging", lambda **_: None)
    generate = Mock(return_value=PlanningRunStats())
    monkeypatch.setattr(coaching_cli, "run_planning_generation", generate)
    coaching_cli.main(["replan", "--user-id", "1"])
    coaching_cli.main(["replan", "--user-id", "1"])
    assert repository.enqueue.call_count == 2 and generate.call_count == 2
    assert all(
        call.kwargs["user_id"] == 1 for call in repository.enqueue.call_args_list
    )
    assert "Queued for background processing" in capsys.readouterr().out


def test_cli_explains_the_weekly_objective(capsys):
    from types import SimpleNamespace

    from test_planning_objective import THRESHOLDS, TODAY, established_training

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
