from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.coaching.llm_client import LlmRateLimitedError
from app.services.planning.generator import PlanningGenerator
from app.services.planning.policy import InsufficientTrainingData
from test_planning_policy import context, payload


def setup_generator():
    repo = Mock()
    request = {"id": 4, "timezone": "Europe/Prague", "attempt_count": 0}
    repo.claim.side_effect = [request, None]
    repo.build_context.return_value = context()
    repo.save_context.return_value = True
    repo.publish.return_value = True
    client = Mock(is_configured=True)
    client.complete_json.return_value = SimpleNamespace(payload=payload(), model="test")
    return (
        PlanningGenerator(
            repository=repo, llm_client=client, today=lambda _: date(2026, 11, 10)
        ),
        repo,
        client,
    )


def test_success_uses_one_call_and_publishes_validated_plan():
    generator, repo, client = setup_generator()
    stats = generator.run(user_id=1)
    assert (stats.generated, stats.calls) == (1, 1)
    repo.publish.assert_called_once()
    client.complete_json.assert_called_once()


def test_missing_key_leaves_queue_untouched():
    generator, repo, client = setup_generator()
    client.is_configured = False
    assert generator.run().skipped_reason == "llm_not_configured"
    repo.claim.assert_not_called()


def test_insufficient_data_does_not_call_model_or_publish():
    generator, repo, client = setup_generator()
    repo.build_context.side_effect = InsufficientTrainingData("No HR data.")
    assert generator.run().insufficient_data == 1
    client.complete_json.assert_not_called()
    repo.finish.assert_called_once_with(
        {"id": 4, "timezone": "Europe/Prague", "attempt_count": 0},
        status="insufficient_data",
        error="No HR data.",
    )


def test_rate_limit_defers_without_incrementing_attempts_and_stops():
    generator, repo, client = setup_generator()
    client.complete_json.side_effect = LlmRateLimitedError(
        "Rate limited", retry_after_seconds=30
    )
    assert generator.run(budget=3).rate_limited
    assert repo.finish.call_args.kwargs == {
        "status": "pending",
        "error": "Rate limited",
        "delay": 30,
    }
    assert repo.claim.call_count == 1


@pytest.mark.parametrize("attempt, status", [(0, "pending"), (4, "failed")])
def test_invalid_answer_retries_then_fails_preserving_previous_plan(attempt, status):
    generator, repo, client = setup_generator()
    repo.claim.side_effect = [
        {"id": 4, "timezone": "Europe/Prague", "attempt_count": attempt}
    ]
    client.complete_json.return_value.payload = {"days": []}
    assert generator.run().failures == 1
    assert repo.finish.call_args.kwargs["status"] == status
    assert repo.finish.call_args.kwargs["attempts"] == attempt + 1
    repo.publish.assert_not_called()


def test_retry_supplies_validation_feedback_to_model():
    generator, repo, client = setup_generator()
    repo.claim.side_effect = [
        {
            "id": 4,
            "timezone": "Europe/Prague",
            "attempt_count": 1,
            "last_error": "Quality work needs recovery spacing.",
        }
    ]
    generator.run()
    assert (
        "Quality work needs recovery spacing."
        in client.complete_json.call_args.kwargs["user_prompt"]
    )
    assert client.complete_json.call_args.kwargs["max_completion_tokens"] == 4096
