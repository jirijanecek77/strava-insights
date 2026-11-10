import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.coaching.llm_client import LlmError, LlmRateLimitedError
from app.services.planning.policy import (
    InsufficientTrainingData,
    build_prompt,
    validate_plan,
)

logger = logging.getLogger(__name__)


@dataclass
class PlanningRunStats:
    generated: int = 0
    calls: int = 0
    failures: int = 0
    rate_limited: bool = False
    insufficient_data: int = 0
    skipped_reason: str | None = None


class PlanningGenerator:
    def __init__(self, *, repository, llm_client, today=None):
        self.repository = repository
        self.llm_client = llm_client
        self.today = today or (lambda timezone: datetime.now(ZoneInfo(timezone)).date())

    def run(self, *, user_id=None, budget=1):
        stats = PlanningRunStats()
        if not self.llm_client.is_configured:
            stats.skipped_reason = "llm_not_configured"
            return stats
        # Bound DB-only work too, e.g. many users lacking usable training history.
        for _ in range(max(0, budget)):
            request = self.repository.claim(user_id=user_id)
            if request is None:
                break
            try:
                today = self.today(request["timezone"])
                context = self.repository.build_context(request, today)
                if request.get("last_error"):
                    context = {
                        **context,
                        "previous_attempt_error": request["last_error"],
                    }
                if context["dates"][-1] <= today.isoformat():
                    raise InsufficientTrainingData(
                        "The requested planning window expired; a new activity or manual replan is needed."
                    )
                if not self.repository.save_context(request, context):
                    continue
                system, user = build_prompt(context)
                stats.calls += 1
                completion = self.llm_client.complete_json(
                    system_prompt=system, user_prompt=user, max_completion_tokens=4096
                )
                days = validate_plan(completion.payload, context)
                if self.repository.publish(
                    request,
                    days,
                    model=completion.model,
                    today=self.today(request["timezone"]),
                ):
                    stats.generated += 1
            except InsufficientTrainingData as exc:
                self.repository.finish(
                    request, status="insufficient_data", error=str(exc)
                )
                stats.insufficient_data += 1
            except LlmRateLimitedError as exc:
                self.repository.finish(
                    request,
                    status="pending",
                    error=str(exc),
                    delay=exc.retry_after_seconds,
                )
                stats.rate_limited = True
                break
            except Exception as exc:
                attempts = request["attempt_count"] + 1
                # Unexpected adapter exceptions may contain credentials/prompt data; never persist their text.
                error = (
                    str(exc)
                    if isinstance(exc, (ValueError, LlmError))
                    else "Planning generation failed."
                )
                self.repository.finish(
                    request,
                    status="failed" if attempts >= 5 else "pending",
                    error=error,
                    delay=(
                        None if attempts >= 5 else min(21600, 60 * 2 ** (attempts - 1))
                    ),
                    attempts=attempts,
                )
                stats.failures += 1
                logger.warning(
                    "Running-plan generation failed for request %s (attempt %s).",
                    request["id"],
                    attempts,
                )
        return stats
