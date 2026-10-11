import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

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

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LlmCompletion: ...


class OpenAICompatibleLlmClient:
    """Calls any OpenAI-compatible chat completions endpoint, e.g. the Gemini API compatibility layer."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: float | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self._model = model or settings.llm_model
        self.reasoning_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else settings.llm_reasoning_effort
        )
        self.http_client = http_client or httpx.Client(
            timeout=timeout_seconds or settings.llm_timeout_seconds
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def complete_json(self, *, system_prompt: str, user_prompt: str) -> LlmCompletion:
        body: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        try:
            response = self.http_client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
        except httpx.HTTPError as exc:
            raise LlmError(f"LLM request failed: {exc}") from exc

        if response.status_code == 429:
            raise LlmRateLimitedError(
                f"LLM rate limit reached: {_error_message(response)}",
                retry_after_seconds=_retry_after_seconds(response),
            )
        if response.status_code >= 400:
            raise LlmError(
                f"LLM request returned HTTP {response.status_code}: {_error_message(response)}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmResponseFormatError("LLM response had no message content.") from exc
        usage = data.get("usage") or {}
        logger.info(
            "LLM completion received.",
            extra={
                "llm.model": self._model,
                "llm.prompt_tokens": usage.get("prompt_tokens"),
                "llm.completion_tokens": usage.get("completion_tokens"),
            },
        )
        return LlmCompletion(payload=parse_json_object(content), model=self._model)


def parse_json_object(content: str | None) -> dict:
    if not content:
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


def _error_message(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:300]
    # The Gemini compatibility layer sometimes wraps the error object in a list.
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
    return str(data)[:300]


def _retry_after_seconds(response: httpx.Response) -> int:
    header = response.headers.get("retry-after")
    if header and header.strip().isdigit():
        return max(1, int(header.strip()))
    # Gemini reports the delay as a google.rpc.RetryInfo detail, e.g. "retryDelay": "37s".
    match = re.search(r'"retryDelay"\s*:\s*"(\d+)(?:\.\d+)?s"', response.text)
    if match:
        return max(1, int(match.group(1)))
    return DEFAULT_RATE_LIMIT_RETRY_SECONDS
