import json
from unittest.mock import Mock

import httpx
import pytest
from ai_fixtures import load_cases, snapshot_for

from app.infrastructure.ai.langchain_groq import LangChainGroqProvider
from app.services.coaching.llm_client import (
    LlmError,
    LlmRateLimitedError,
    LlmResponseFormatError,
)


@pytest.fixture
def snapshot():
    return snapshot_for("activity-controlled")


def response(payload=None, finish="stop"):
    return {
        "id": "safe-request",
        "object": "chat.completion",
        "created": 1,
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        payload
                        or {
                            "description": "Solid running.",
                            "summary": "Aerobic stimulus.",
                            "recommendation": "Recover.",
                        }
                    ),
                },
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
    }


def test_one_native_schema_http_attempt_preserves_usage_and_disables_environment_tracing(
    snapshot, monkeypatch
):
    import socket

    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setattr(
        socket.socket,
        "connect",
        lambda *a: pytest.fail("Unexpected external tracing/network"),
    )
    calls = []

    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=response())

    recorder = Mock()
    recorder.begin.return_value = "attempt-1"
    with_provider = LangChainGroqProvider(
        recorder, api_key="synthetic", transport=httpx.MockTransport(handle)
    )
    try:
        result = with_provider.generate(snapshot)
        assert result.value.summary == "Aerobic stimulus."
        assert result.usage.total_tokens == 120
        assert with_provider.attempts == len(calls) == 1
        schema = calls[0]["response_format"]
        assert (
            schema["type"] == "json_schema" and schema["json_schema"]["strict"] is True
        )
        assert schema["json_schema"]["schema"]["additionalProperties"] is False
        assert calls[0]["temperature"] == 1
        assert calls[0]["max_tokens"] == 2048
        recorder.begin.assert_called_once()
        assert recorder.finish.call_args.kwargs["outcome"] == "success"
    finally:
        with_provider.close()


@pytest.mark.parametrize(
    "scenario,expected",
    [
        ("429", LlmRateLimitedError),
        ("400", LlmError),
        ("500", LlmError),
        ("timeout", LlmError),
        ("invalid", LlmResponseFormatError),
        ("truncated", LlmResponseFormatError),
    ],
)
def test_failures_make_one_accounted_http_request_without_inner_retry(
    snapshot, scenario, expected
):
    calls = []

    def handle(request):
        calls.append(request)
        if scenario == "timeout":
            raise httpx.ReadTimeout("sensitive transport detail")
        if scenario in {"429", "400", "500"}:
            return httpx.Response(
                int(scenario),
                json={
                    "error": {
                        "message": "private prompt and credential",
                        "type": "invalid_value",
                    }
                },
                headers={"retry-after": "30"},
            )
        return httpx.Response(
            200,
            json=(
                response({"wrong": "private content"})
                if scenario == "invalid"
                else response(finish="length")
            ),
        )

    recorder = Mock()
    recorder.begin.return_value = "attempt-1"
    provider = LangChainGroqProvider(
        recorder, api_key="synthetic", transport=httpx.MockTransport(handle)
    )
    try:
        with pytest.raises(expected) as error:
            provider.generate(snapshot)
        assert "private" not in str(error.value) and "sensitive" not in str(error.value)
        assert provider.attempts == len(calls) == 1
        recorder.begin.assert_called_once()
        recorder.finish.assert_called_once()
        if scenario in {"429", "400", "500"}:
            assert recorder.finish.call_args.kwargs["usage"].http_status == int(
                scenario
            )
            assert (
                recorder.finish.call_args.kwargs["usage"].error_type == "invalid_value"
            )
        if scenario == "truncated":
            assert recorder.finish.call_args.kwargs["usage"].total_tokens == 120
    finally:
        provider.close()


def test_missing_key_does_not_start_attempt(snapshot):
    recorder = Mock()
    provider = LangChainGroqProvider(recorder, api_key="")
    try:
        with pytest.raises(LlmError):
            provider.generate(snapshot)
        recorder.begin.assert_not_called()
        assert provider.attempts == 0
    finally:
        provider.close()


def test_expired_owner_is_rejected_before_http_without_becoming_a_transport_failure(
    snapshot,
):
    from app.services.ai.contracts import ObsoleteWork

    recorder = Mock()
    recorder.begin.side_effect = ObsoleteWork("Owner changed")
    requests = []
    provider = LangChainGroqProvider(
        recorder,
        api_key="synthetic",
        transport=httpx.MockTransport(lambda request: requests.append(request)),
    )
    try:
        with pytest.raises(ObsoleteWork):
            provider.generate(snapshot)
        assert not requests and provider.attempts == 0
        recorder.finish.assert_not_called()
    finally:
        provider.close()


@pytest.mark.parametrize(
    "case_id,expected_version",
    [
        ("week-balanced", "5-g3"),
        ("month-incomplete", "5-g4-incomplete"),
        ("plan-supported", "3"),
    ],
)
def test_native_period_and_plan_schemas_keep_their_typed_envelope_and_one_call(
    case_id, expected_version
):
    from app.services.ai.contracts import PeriodResult, PlanResult

    case = next(case for case in load_cases() if case.id == case_id)
    prepared = snapshot_for(case_id)
    payload = (
        {
            "days": [
                {
                    "date": str(day),
                    "kind": "rest",
                    "focus": "rest",
                    "distance_km": None,
                    "pace_seconds_per_km": None,
                    "heart_rate_bpm": None,
                    "rationale": "Schema transport fixture.",
                }
                for day in prepared.context.dates
            ]
        }
        if case.kind == "plan"
        else {"summary": "Evidence is limited.", "recommendation": "Allow recovery."}
    )
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=response(payload))

    recorder = Mock()
    recorder.begin.return_value = "typed-attempt"
    provider = LangChainGroqProvider(
        recorder, api_key="synthetic", transport=httpx.MockTransport(handle)
    )
    try:
        result = provider.generate(prepared)
        assert isinstance(
            result.value, PlanResult if case.kind == "plan" else PeriodResult
        )
        assert provider.attempts == len(requests) == 1
        assert requests[0]["max_tokens"] == prepared.completion_limit
        assert requests[0]["response_format"]["json_schema"]["strict"] is True
        assert recorder.begin.call_args.args[0].prompt_version == expected_version
        assert requests[0]["messages"][1]["content"] == prepared.user_prompt
    finally:
        provider.close()
