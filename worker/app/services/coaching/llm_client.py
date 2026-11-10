import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

import groq
from groq import Groq

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_RATE_LIMIT_RETRY_SECONDS = 15 * 60


class LlmError(Exception):
    """A failed LLM request that may succeed when retried later."""


class LlmRateLimitedError(LlmError):
    def __init__(self, message: str, *, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class LlmResponseFormatError(LlmError):
    """The model answered, but not with the JSON object the prompt asked for."""


@dataclass(frozen=True, slots=True)
class LlmCompletion:
    payload: dict
    model: str


class LlmClient(Protocol):
    @property
    def model(self) -> str: ...

    def complete_json(
        self, *, system_prompt: str, user_prompt: str, max_completion_tokens: int = 2048
    ) -> LlmCompletion: ...


class GroqLlmClient:
    """Groq SDK adapter; durable coaching work items own retries."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        sdk_client: Groq | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self._model = model or settings.llm_model
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.llm_timeout_seconds
        )
        self._sdk_client = sdk_client
        self._owns_client = sdk_client is None

    @property
    def model(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def close(self) -> None:
        if self._owns_client and self._sdk_client is not None:
            self._sdk_client.close()
            self._sdk_client = None

    def complete_json(self, *, system_prompt: str, user_prompt: str, max_completion_tokens: int = 2048) -> LlmCompletion:
        if not self.is_configured:
            raise LlmError("Groq API key is not configured.")
        if self._sdk_client is None:
            self._sdk_client = Groq(
                api_key=self.api_key,
                timeout=self.timeout_seconds,
                max_retries=0,
            )
        try:
            response = self._sdk_client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=max_completion_tokens,
            )
        except groq.RateLimitError as exc:
            raise LlmRateLimitedError(
                "Groq rate limit reached (HTTP 429).",
                retry_after_seconds=_retry_after_seconds(
                    exc.response.headers.get("retry-after")
                ),
            ) from None
        except groq.APIStatusError as exc:
            # Provider error bodies can echo prompt content. Do not persist or log them.
            raise LlmError(f"Groq request returned HTTP {exc.status_code}.") from None
        except groq.APITimeoutError:
            raise LlmError("Groq request timed out.") from None
        except groq.APIConnectionError:
            raise LlmError("Groq connection failed.") from None
        except groq.APIError:
            raise LlmError("Groq request failed.") from None
        except ValueError:
            raise LlmResponseFormatError("Groq response was not valid JSON.") from None

        try:
            choice = response.choices[0]
            content = choice.message.content
            finish_reason = choice.finish_reason
        except (AttributeError, IndexError, TypeError):
            raise LlmResponseFormatError(
                "LLM response had no message content."
            ) from None
        if finish_reason != "stop":
            raise LlmResponseFormatError("LLM response did not finish normally.")
        usage = response.usage
        logger.info(
            "LLM completion received.",
            extra={
                "llm.model": self._model,
                "llm.prompt_tokens": usage.prompt_tokens if usage else None,
                "llm.completion_tokens": usage.completion_tokens if usage else None,
            },
        )
        return LlmCompletion(payload=parse_json_object(content), model=self._model)


def parse_json_object(content: str | None) -> dict:
    if not isinstance(content, str) or not content.strip():
        raise LlmResponseFormatError("LLM response was empty.")
    text = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise LlmResponseFormatError("LLM response was not JSON.") from None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LlmResponseFormatError("LLM response was not JSON.") from exc
    if not isinstance(parsed, dict):
        raise LlmResponseFormatError("LLM response JSON was not an object.")
    return parsed


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
