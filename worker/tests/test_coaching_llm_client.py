import json
import logging
import traceback
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from groq import Groq

from app.config import Settings
from app.services.coaching import llm_client as llm_module
from app.services.coaching.llm_client import (
    DEFAULT_RATE_LIMIT_RETRY_SECONDS,
    GroqLlmClient,
    LlmError,
    LlmRateLimitedError,
    LlmResponseFormatError,
    parse_json_object,
)


def _response(content='{"summary": "Easy run."}', *, finish_reason="stop"):
    return {
        "id": "chat-test",
        "object": "chat.completion",
        "created": 1,
        "model": "openai/gpt-oss-120b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
    }


@pytest.fixture
def make_client(monkeypatch):
    clients = []

    def factory(handler):
        def sdk_factory(**kwargs):
            sdk = Groq(
                **kwargs,
                http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            )
            clients.append(sdk)
            return sdk

        monkeypatch.setattr(llm_module, "Groq", sdk_factory)
        client = GroqLlmClient(api_key="test-secret", timeout_seconds=17)
        return client

    yield factory
    for sdk in clients:
        sdk.close()


def test_sdk_request_json_parsing_usage_and_owned_cleanup(make_client, caplog):
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        captured["timeout"] = request.extensions["timeout"]
        return httpx.Response(
            200, json=_response('```json\n{"summary": "Easy run."}\n```')
        )

    client = make_client(handler)
    with caplog.at_level(logging.INFO):
        completion = client.complete_json(
            system_prompt="Return JSON as a coach", user_prompt="data"
        )

    assert completion.payload == {"summary": "Easy run."}
    assert completion.model == "openai/gpt-oss-120b"
    assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert captured["auth"] == "Bearer test-secret"
    assert captured["body"] == {
        "model": "openai/gpt-oss-120b",
        "messages": [
            {"role": "system", "content": "Return JSON as a coach"},
            {"role": "user", "content": "data"},
        ],
        "response_format": {"type": "json_object"},
        "max_completion_tokens": 2048,
    }
    assert captured["timeout"]["read"] == 17
    record = next(
        record
        for record in caplog.records
        if record.message == "LLM completion received."
    )
    assert record.__dict__["llm.prompt_tokens"] == 30
    assert record.__dict__["llm.completion_tokens"] == 10
    sdk = client._sdk_client
    assert sdk.max_retries == 0
    client.close()
    assert sdk.is_closed()
    client.close()


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("120", 120),
        ("0.1", 1),
        ("37.2", 38),
        ("0", 1),
        (None, 900),
        ("nonsense", 900),
        ("NaN", 900),
        ("inf", 900),
        ("-10", 900),
    ],
)
def test_rate_limit_retry_after_and_no_sdk_retries(make_client, header, expected):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            429,
            headers={"retry-after": header} if header else {},
            json={"error": {"message": "private provider details"}},
        )

    client = make_client(handler)
    with pytest.raises(LlmRateLimitedError) as error:
        client.complete_json(system_prompt="coach", user_prompt="data")
    assert error.value.retry_after_seconds == expected
    assert len(requests) == 1
    assert "private provider details" not in "".join(
        traceback.format_exception(error.value)
    )
    sdk = client._sdk_client
    client.close()
    assert sdk.is_closed()


def test_rate_limit_http_date(make_client):
    retry_at = datetime.now(UTC) + timedelta(seconds=120)
    client = make_client(
        lambda _: httpx.Response(
            429, headers={"retry-after": format_datetime(retry_at)}
        )
    )
    with pytest.raises(LlmRateLimitedError) as error:
        client.complete_json(system_prompt="coach", user_prompt="data")
    assert 119 <= error.value.retry_after_seconds <= 120


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 500, 503])
def test_status_errors_are_sanitized_and_not_retried_by_sdk(make_client, status):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, json={"error": {"message": "private prompt and test-secret"}}
        )

    with pytest.raises(LlmError, match=f"HTTP {status}") as error:
        make_client(handler).complete_json(system_prompt="coach", user_prompt="data")
    assert len(requests) == 1
    assert "private prompt" not in "".join(traceback.format_exception(error.value))
    assert "test-secret" not in str(error.value)


@pytest.mark.parametrize(
    ("error_type", "message"),
    [(httpx.ConnectError, "connection failed"), (httpx.ReadTimeout, "timed out")],
)
def test_network_errors_are_retryable_without_sdk_retries(
    make_client, error_type, message
):
    requests = []

    def handler(request):
        requests.append(request)
        raise error_type("private transport details", request=request)

    with pytest.raises(LlmError, match=message):
        make_client(handler).complete_json(system_prompt="coach", user_prompt="data")
    assert len(requests) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"choices": []},
        {"choices": None},
        {},
        {"choices": [{"message": None}]},
        _response(None),
        _response(""),
        _response("   "),
        _response("not JSON"),
        _response("[]"),
        _response('{"summary": "valid but truncated"}', finish_reason="length"),
        _response('{"summary": "filtered"}', finish_reason="content_filter"),
    ],
)
def test_bad_or_incomplete_responses_are_format_failures(make_client, payload):
    with pytest.raises(LlmResponseFormatError):
        make_client(lambda _: httpx.Response(200, json=payload)).complete_json(
            system_prompt="coach", user_prompt="data"
        )


def test_non_json_http_response_is_format_failure(make_client):
    with pytest.raises(LlmResponseFormatError):
        make_client(
            lambda _: httpx.Response(200, text="invalid upstream response")
        ).complete_json(system_prompt="coach", user_prompt="data")


def test_missing_usage_is_allowed(make_client):
    payload = _response()
    del payload["usage"]
    result = make_client(lambda _: httpx.Response(200, json=payload)).complete_json(
        system_prompt="coach", user_prompt="data"
    )
    assert result.payload["summary"] == "Easy run."


def test_missing_key_does_not_construct_sdk(monkeypatch):
    def unexpected_sdk(**kwargs):
        pytest.fail("SDK must not be constructed without an API key")

    monkeypatch.setattr(llm_module, "Groq", unexpected_sdk)
    client = GroqLlmClient(api_key="")
    assert not client.is_configured
    with pytest.raises(LlmError, match="not configured"):
        client.complete_json(system_prompt="coach", user_prompt="data")
    client.close()


def test_settings_default_to_no_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert Settings(_env_file=None).llm_api_key == ""


def test_borrowed_sdk_is_not_closed():
    with Groq(
        api_key="test-secret",
        max_retries=0,
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=_response())
            )
        ),
    ) as sdk:
        client = GroqLlmClient(
            api_key="test-secret", sdk_client=sdk, model="custom-model"
        )
        assert (
            client.complete_json(system_prompt="coach", user_prompt="data").model
            == "custom-model"
        )
        client.close()
        assert not sdk.is_closed()


def test_parse_json_object():
    assert parse_json_object('Here you go: {"a": 1} thanks') == {"a": 1}
    for value in ("[1, 2]", "", None, "broken {JSON}"):
        with pytest.raises(LlmResponseFormatError):
            parse_json_object(value)
    assert DEFAULT_RATE_LIMIT_RETRY_SECONDS == 900
