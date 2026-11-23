"""One native-schema request, with retries and persistence owned by the application."""

import logging
import time

import groq
import httpx
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langsmith import tracing_context
from pydantic import SecretStr

from app.config import settings
from app.services.ai.contracts import (
    ActivityResult,
    AttemptRecorder,
    GeneratedResult,
    InputSnapshot,
    Operation,
    PeriodResult,
    PlanResult,
    ProviderUsage,
)
from app.services.ai.grounding import grounded_snapshot
from app.services.coaching.evidence import fingerprint
from app.services.coaching.llm_client import (
    LlmError,
    LlmRateLimitedError,
    LlmResponseFormatError,
    ProviderFailure,
    _retry_after_seconds,
    _safe_request_id,
)

logger = logging.getLogger(__name__)
SCHEMAS: dict[
    Operation, type[ActivityResult] | type[PeriodResult] | type[PlanResult]
] = {
    Operation.ACTIVITY: ActivityResult,
    Operation.WEEK: PeriodResult,
    Operation.MONTH: PeriodResult,
    Operation.PLAN: PlanResult,
}


class LangChainGroqProvider:
    def __init__(
        self,
        recorder: AttemptRecorder,
        *,
        api_key=None,
        model=None,
        timeout=None,
        transport=None,
    ):
        self.api_key = settings.llm_api_key if api_key is None else api_key
        self.model = model or settings.llm_model
        self.timeout = settings.llm_timeout_seconds if timeout is None else timeout
        self.recorder = recorder
        self.attempts = 0
        self._snapshot: InputSnapshot | None = None
        self._attempt_id = None
        self._blocked_exception = None
        self._request_id = None
        self._http_status: int | None = None
        self._metadata = ProviderUsage(integration_version="langchain-native-v1")
        self._http = httpx.Client(
            timeout=self.timeout,
            transport=transport,
            follow_redirects=False,
            event_hooks={
                "request": [self._before_request],
                "response": [self._after_response],
            },
        )

    @property
    def is_configured(self):
        return bool(self.api_key)

    def close(self):
        self._http.close()

    def _before_request(self, request):
        if self._snapshot is None or self._attempt_id is not None:
            raise LlmError("Unexpected extra provider request was blocked")
        try:
            self._attempt_id = self.recorder.begin(
                self._snapshot, model=self.model, metadata=self._metadata
            )
        except Exception as exc:
            self._blocked_exception = exc
            raise
        self.attempts += 1

    def _after_response(self, response):
        self._request_id = _safe_request_id(response.headers.get("x-request-id"))
        self._http_status = response.status_code

    def generate(self, snapshot: InputSnapshot) -> GeneratedResult:
        if not self.is_configured:
            raise LlmError("Groq API key is not configured")
        if self._snapshot is not None:
            raise LlmError("A provider instance cannot run concurrent attempts")
        snapshot = grounded_snapshot(snapshot)
        self._snapshot, self._attempt_id, self._blocked_exception = snapshot, None, None
        self._request_id = None
        self._http_status = None
        started = time.perf_counter()
        self._metadata = ProviderUsage(
            integration_version=(
                "langchain-native-v2-grounded"
                if snapshot.claim.operation != Operation.PLAN
                else "langchain-native-v1"
            ),
            schema_fingerprint=fingerprint(
                SCHEMAS[snapshot.claim.operation].model_json_schema()
            ),
        )
        usage, outcome = self._metadata, "unknown"
        try:
            chat = ChatGroq(
                model=self.model,
                api_key=SecretStr(self.api_key),
                timeout=self.timeout,
                max_retries=0,
                max_tokens=snapshot.completion_limit,
                temperature=1.0,
                http_client=self._http,
            )
            structured = chat.with_structured_output(
                SCHEMAS[snapshot.claim.operation],
                method="json_schema",
                strict=True,
                include_raw=True,
            )
            prompt = ChatPromptTemplate.from_messages(
                [("system", "{system}"), ("human", "{input}")]
            )
            # Suppress tracing even if inherited shell configuration enables it.
            with tracing_context(enabled=False):
                response = (prompt | structured).invoke(
                    {"system": snapshot.system_prompt, "input": snapshot.user_prompt},
                    config={"callbacks": []},
                )
            if not isinstance(response, dict):
                outcome = "structure_failure"
                raise LlmResponseFormatError(
                    "Provider returned an invalid structured envelope"
                )
            raw = response["raw"]
            tokens = raw.usage_metadata or {}
            finish = raw.response_metadata.get("finish_reason")
            usage = ProviderUsage(
                integration_version=self._metadata.integration_version,
                schema_fingerprint=self._metadata.schema_fingerprint,
                input_tokens=tokens.get("input_tokens"),
                output_tokens=tokens.get("output_tokens"),
                total_tokens=tokens.get("total_tokens"),
                finish_reason=(
                    finish
                    if finish in {"stop", "length", "content_filter", "tool_calls"}
                    else None
                ),
                request_id=self._request_id,
                http_status=self._http_status,
            )
            if (
                finish != "stop"
                or response["parsing_error"] is not None
                or response["parsed"] is None
            ):
                outcome = "structure_failure"
                raise LlmResponseFormatError(
                    "Provider returned an incomplete or invalid structured response"
                )
            value = SCHEMAS[snapshot.claim.operation].model_validate(
                response["parsed"].model_dump()
            )
            outcome = "success"
            return GeneratedResult(
                value,
                raw.response_metadata.get("model_name", self.model),
                usage.model_copy(
                    update={"latency_ms": (time.perf_counter() - started) * 1000}
                ),
                self._attempt_id,
            )
        except groq.RateLimitError as exc:
            outcome = "rate_limited"
            failure = ProviderFailure.from_error(exc)
            usage = usage.model_copy(
                update={
                    "request_id": failure.request_id,
                    "http_status": failure.status,
                    "error_code": failure.code,
                    "error_type": failure.error_type,
                }
            )
            raise LlmRateLimitedError(
                "Groq rate limit reached (HTTP 429)",
                retry_after_seconds=_retry_after_seconds(
                    exc.response.headers.get("retry-after")
                ),
            ) from None
        except groq.APIStatusError as exc:
            outcome = "provider_failure"
            failure = ProviderFailure.from_error(exc)
            usage = usage.model_copy(
                update={
                    "request_id": failure.request_id,
                    "http_status": failure.status,
                    "error_code": failure.code,
                    "error_type": failure.error_type,
                }
            )
            logger.warning(
                "Provider rejected structured request",
                extra={
                    "llm.status_code": failure.status,
                    "llm.error_code": failure.code,
                    "llm.error_type": failure.error_type,
                },
            )
            raise LlmError(f"Groq request returned HTTP {failure.status}") from None
        except groq.APIError:
            if self._blocked_exception is not None:
                raise self._blocked_exception from None
            outcome = "transport_failure"
            raise LlmError("Groq request failed during transport") from None
        finally:
            usage = usage.model_copy(
                update={"latency_ms": (time.perf_counter() - started) * 1000}
            )
            try:
                if self._attempt_id is not None:
                    self.recorder.finish(self._attempt_id, outcome=outcome, usage=usage)
                    logger.info(
                        "AI provider attempt finished",
                        extra={
                            "ai.operation": snapshot.claim.operation.value,
                            "ai.work_id": snapshot.claim.id,
                            "user.id": snapshot.claim.user_id,
                            "ai.attempt_id": self._attempt_id,
                            "ai.input_revision": snapshot.revision,
                            "ai.prompt_version": snapshot.prompt_version,
                            "llm.model": self.model,
                            "ai.outcome": outcome,
                            "duration_ms": round(usage.latency_ms, 2),
                            "llm.prompt_tokens": usage.input_tokens,
                            "llm.completion_tokens": usage.output_tokens,
                        },
                    )
            finally:
                self._snapshot, self._attempt_id, self._blocked_exception = (
                    None,
                    None,
                    None,
                )
