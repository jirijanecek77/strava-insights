from unittest.mock import Mock

import pytest

from app.services.coaching.generator import CoachingRunStats
from app.tasks import coaching


@pytest.mark.parametrize("fails", [False, True])
def test_generation_closes_client_and_session_even_on_failure(monkeypatch, fails):
    session, client, generator = Mock(), Mock(), Mock()
    generator.run.return_value = CoachingRunStats()
    if fails:
        generator.run.side_effect = RuntimeError("generation failed")
    monkeypatch.setattr(coaching, "SessionLocal", lambda: session)
    monkeypatch.setattr(coaching, "GroqLlmClient", lambda: client)
    monkeypatch.setattr(coaching, "CoachingRepository", Mock())
    monkeypatch.setattr(coaching, "CoachingGenerator", Mock(return_value=generator))

    if fails:
        with pytest.raises(RuntimeError, match="generation failed"):
            coaching.run_coaching_generation(user_id=1)
    else:
        assert coaching.run_coaching_generation(user_id=1) == CoachingRunStats()
    client.close.assert_called_once()
    session.close.assert_called_once()
