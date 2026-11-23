"""Shared production provider failures and retry-delay handling."""

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import groq

DEFAULT_RATE_LIMIT_RETRY_SECONDS = 15 * 60
_ERROR_CODES = frozenset(
    {
        "json_validate_failed",
        "context_length_exceeded",
        "rate_limit_exceeded",
        "invalid_api_key",
        "model_not_found",
        "permission_denied",
        "invalid_request_error",
        "invalid_value",
        "unsupported_parameter",
        "insufficient_quota",
        "authentication_error",
    }
)


def _safe_request_id(value) -> str | None:
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value)
        else None
    )


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    status: int
    code: str | None
    error_type: str | None
    request_id: str | None

    @classmethod
    def from_error(cls, error: groq.APIStatusError):
        body = error.body if isinstance(error.body, dict) else {}
        details = body.get("error", body)
        details = details if isinstance(details, dict) else {}
        code, kind = details.get("code"), details.get("type")
        return cls(
            error.status_code,
            code if isinstance(code, str) and code in _ERROR_CODES else None,
            kind if isinstance(kind, str) and kind in _ERROR_CODES else None,
            _safe_request_id(error.response.headers.get("x-request-id")),
        )


class LlmError(Exception):
    """A failed LLM request that may succeed when retried later."""


class LlmRateLimitedError(LlmError):
    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LlmResponseFormatError(LlmError):
    """The provider returned an incomplete or invalid structured response."""


def _retry_after_seconds(header: str | None) -> int:
    if header:
        try:
            delay = float(header)
            if math.isfinite(delay) and delay >= 0:
                return max(1, math.ceil(delay))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(header)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                return max(1, math.ceil((retry_at - datetime.now(UTC)).total_seconds()))
            except (ValueError, TypeError, OverflowError):
                pass
    return DEFAULT_RATE_LIMIT_RETRY_SECONDS
