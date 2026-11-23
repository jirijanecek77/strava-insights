"""Production provider diagnostics and retry policy without any provider requests."""

from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import groq
import httpx
import pytest

from app.config import Settings
from app.services.coaching import llm_client
from app.services.coaching.llm_client import ProviderFailure, _retry_after_seconds


@pytest.mark.parametrize(
    "header,expected",
    [
        (None, 900),
        ("", 900),
        ("broken", 900),
        ("-1", 900),
        ("nan", 900),
        ("inf", 900),
        ("0", 1),
        ("0.2", 1),
        ("30", 30),
        ("1.1", 2),
    ],
)
def test_retry_headers_use_bounded_fallback_and_round_up(header, expected):
    assert _retry_after_seconds(header) == expected


def test_retry_http_date_uses_utc_and_never_returns_zero(monkeypatch):
    now = datetime(2026, 11, 24, 9, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(llm_client, "datetime", Clock)
    assert _retry_after_seconds(format_datetime(now + timedelta(seconds=65))) == 65
    assert _retry_after_seconds(format_datetime(now - timedelta(seconds=5))) == 1


@pytest.mark.parametrize("trusted", [True, False])
def test_provider_failure_retains_only_allowlisted_diagnostics(trusted):
    response = httpx.Response(
        400,
        request=httpx.Request("POST", "https://example.invalid/completions"),
        headers={"x-request-id": "req-safe-12" if trusted else "private athlete notes"},
    )
    error = groq.BadRequestError(
        "private prompt and credential",
        response=response,
        body={
            "error": {
                "code": "json_validate_failed" if trusted else "private prompt",
                "type": "invalid_request_error" if trusted else "private credential",
                "message": "private prompt",
                "failed_generation": "private output",
            }
        },
    )
    failure = ProviderFailure.from_error(error)
    assert failure.status == 400
    assert failure.code == ("json_validate_failed" if trusted else None)
    assert failure.error_type == ("invalid_request_error" if trusted else None)
    assert failure.request_id == ("req-safe-12" if trusted else None)
    assert "private" not in repr(failure)


@pytest.mark.parametrize("body", [None, [], "private body", {"error": []}])
def test_unstructured_provider_error_bodies_are_not_exposed(body):
    response = httpx.Response(
        500, request=httpx.Request("POST", "https://example.invalid/completions")
    )
    failure = ProviderFailure.from_error(
        groq.InternalServerError("private", response=response, body=body)
    )
    assert (failure.code, failure.error_type, failure.request_id) == (None, None, None)


def test_settings_default_to_no_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert Settings(_env_file=None).llm_api_key == ""
