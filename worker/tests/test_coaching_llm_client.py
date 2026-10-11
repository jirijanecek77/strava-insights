import json

import httpx
import pytest

from app.services.coaching.llm_client import (
    DEFAULT_RATE_LIMIT_RETRY_SECONDS,
    LlmError,
    LlmRateLimitedError,
    LlmResponseFormatError,
    OpenAICompatibleLlmClient,
    parse_json_object,
)


def _client(handler) -> OpenAICompatibleLlmClient:
    return OpenAICompatibleLlmClient(
        base_url="https://llm.example/v1beta/openai/",
        api_key="secret",
        model="gemini-test",
        reasoning_effort="low",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_complete_json_posts_an_openai_compatible_request_and_parses_fenced_json() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["authorization"]
        captured["body"] = json.loads(request.content)
        content = '```json\n{"summary": "Easy run."}\n```'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}], "usage": {}})

    completion = _client(handler).complete_json(system_prompt="coach", user_prompt="data")

    assert completion.payload == {"summary": "Easy run."}
    assert completion.model == "gemini-test"
    assert captured["url"] == "https://llm.example/v1beta/openai/chat/completions"
    assert captured["auth"] == "Bearer secret"
    assert captured["body"]["model"] == "gemini-test"
    assert captured["body"]["response_format"] == {"type": "json_object"}
    assert captured["body"]["reasoning_effort"] == "low"
    assert [message["role"] for message in captured["body"]["messages"]] == ["system", "user"]


def test_rate_limit_uses_gemini_retry_delay() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json=[
                {
                    "error": {
                        "code": 429,
                        "message": "Quota exceeded",
                        "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "37s"}],
                    }
                }
            ],
        )

    with pytest.raises(LlmRateLimitedError) as error:
        _client(handler).complete_json(system_prompt="coach", user_prompt="data")

    assert error.value.retry_after_seconds == 37
    assert "Quota exceeded" in str(error.value)


def test_rate_limit_falls_back_to_retry_after_header_or_default() -> None:
    with pytest.raises(LlmRateLimitedError) as with_header:
        _client(lambda _request: httpx.Response(429, headers={"retry-after": "120"}, text="slow down")).complete_json(
            system_prompt="coach", user_prompt="data"
        )
    assert with_header.value.retry_after_seconds == 120

    with pytest.raises(LlmRateLimitedError) as without_hint:
        _client(lambda _request: httpx.Response(429, text="slow down")).complete_json(
            system_prompt="coach", user_prompt="data"
        )
    assert without_hint.value.retry_after_seconds == DEFAULT_RATE_LIMIT_RETRY_SECONDS


def test_server_errors_and_bad_payloads_raise_retryable_errors() -> None:
    with pytest.raises(LlmError, match="HTTP 503"):
        _client(lambda _request: httpx.Response(503, json={"error": {"message": "overloaded"}})).complete_json(
            system_prompt="coach", user_prompt="data"
        )
    with pytest.raises(LlmResponseFormatError):
        _client(lambda _request: httpx.Response(200, json={"choices": []})).complete_json(
            system_prompt="coach", user_prompt="data"
        )


def test_parse_json_object_extracts_the_object_from_surrounding_text() -> None:
    assert parse_json_object('Here you go: {"a": 1} thanks') == {"a": 1}
    with pytest.raises(LlmResponseFormatError):
        parse_json_object("[1, 2]")
    with pytest.raises(LlmResponseFormatError):
        parse_json_object("")
