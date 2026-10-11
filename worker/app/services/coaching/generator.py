import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable

from app.services.coaching.context_builder import (
    CoachingContextBuilder,
    period_start_for,
)
from app.services.coaching.llm_client import LlmClient, LlmRateLimitedError
from app.services.coaching.prompts import (
    PROMPT_VERSION,
    build_activity_prompt,
    build_period_prompt,
    parse_activity_narrative,
    parse_period_review,
)

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
MAX_RETRY_DELAY_SECONDS = 6 * 60 * 60
PERIOD_PLANNING_WINDOW_DAYS = 70
PERIOD_TYPES = ("week", "month")


@dataclass
class CoachingRunStats:
    activity_notes_generated: int = 0
    period_summaries_generated: int = 0
    failures: int = 0
    rate_limited: bool = False
    skipped_reason: str | None = None
    periods_planned: list[tuple[int, str, date]] = field(default_factory=list)


class _StopRun(Exception):
    pass


class CoachingGenerator:
    """Generates pending activity coaching notes, then refreshes the affected week and month reviews."""

    def __init__(
        self,
        *,
        repository: Any,
        llm_client: LlmClient,
        context_builder: CoachingContextBuilder | None = None,
        is_configured: bool = True,
        batch_size: int = 5,
        today: Callable[[], date] | None = None,
    ) -> None:
        self.repository = repository
        self.llm_client = llm_client
        self.context_builder = context_builder or CoachingContextBuilder(repository)
        self.is_configured = is_configured
        self.batch_size = batch_size
        self.today = today or (lambda: datetime.now(UTC).date())

    def run(self, *, user_id: int | None = None) -> CoachingRunStats:
        stats = CoachingRunStats()
        if not self.is_configured:
            stats.skipped_reason = "llm_not_configured"
            logger.info("Skipping AI coaching generation because no LLM API key is configured.")
            return stats

        budget = self.batch_size
        try:
            while budget > 0:
                note = self.repository.claim_next_activity_note(user_id=user_id)
                if note is None:
                    break
                budget -= 1
                self._generate_activity_note(note, stats)

            stats.periods_planned = self._plan_periods(user_id=user_id)

            while budget > 0:
                period = self.repository.claim_next_period(user_id=user_id)
                if period is None:
                    break
                budget -= 1
                self._generate_period(period, stats)
        except _StopRun:
            stats.rate_limited = True
        logger.info(
            "Finished AI coaching generation run.",
            extra={
                "user.id": user_id,
                "coaching.activity_notes_generated": stats.activity_notes_generated,
                "coaching.period_summaries_generated": stats.period_summaries_generated,
                "coaching.failures": stats.failures,
                "coaching.rate_limited": stats.rate_limited,
            },
        )
        return stats

    def _generate_activity_note(self, note, stats: CoachingRunStats) -> None:
        try:
            context = self.context_builder.build_activity_context(
                user_id=note.user_id, activity_id=note.activity_id
            )
            if context is None:
                self.repository.mark_failed(
                    note, error_message="Activity no longer exists.", attempt_count=note.attempt_count + 1
                )
                stats.failures += 1
                return
            system_prompt, user_prompt = build_activity_prompt(context)
            completion = self.llm_client.complete_json(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
            narrative = parse_activity_narrative(completion.payload)
        except Exception as exc:
            self._handle_failure(note, exc, stats, label="activity coaching note")
            return
        self.repository.mark_activity_note_ready(
            note,
            description=narrative.description,
            summary=narrative.summary,
            recommendation=narrative.recommendation,
            model=completion.model,
            prompt_version=PROMPT_VERSION,
        )
        stats.activity_notes_generated += 1
        logger.info(
            "Generated activity coaching note.",
            extra={"user.id": note.user_id, "activity.id": note.activity_id},
        )

    def _plan_periods(self, *, user_id: int | None) -> list[tuple[int, str, date]]:
        """Queue week and month reviews whose inputs changed or that ended since their last review."""
        today = self.today()
        since = today - timedelta(days=PERIOD_PLANNING_WINDOW_DAYS)
        planned: list[tuple[int, str, date]] = []
        for candidate_user_id in self.repository.list_users_with_recent_notes(
            since=since, user_id=user_id
        ):
            period_keys = sorted(
                {
                    (period_type, period_start_for(period_type, start.date()))
                    for start in self.repository.list_recent_note_activity_dates(
                        user_id=candidate_user_id, since=since
                    )
                    for period_type in PERIOD_TYPES
                }
            )
            for period_type, period_start in period_keys:
                period_context = self.context_builder.build_period_context(
                    user_id=candidate_user_id,
                    period_type=period_type,
                    period_start=period_start,
                    today=today,
                )
                # Wait until every activity note in the period is done, so the review sees all summaries.
                if period_context.has_pending_notes or not period_context.has_ready_notes:
                    continue
                period = self.repository.get_or_create_period(
                    user_id=candidate_user_id, period_type=period_type, period_start=period_start
                )
                already_queued = period.status in {"pending", "generating"}
                inputs_unchanged = period.source_hash == period_context.source_hash
                needs_final_review = period_context.is_final and not period.is_final
                if already_queued or (
                    inputs_unchanged and (period.status == "failed" or not needs_final_review)
                ):
                    self.repository.commit()
                    continue
                self.repository.mark_period_pending(period)
                planned.append((candidate_user_id, period_type, period_start))
        return planned

    def _generate_period(self, period, stats: CoachingRunStats) -> None:
        source_hash = None
        try:
            period_context = self.context_builder.build_period_context(
                user_id=period.user_id,
                period_type=period.period_type,
                period_start=period.period_start,
                today=self.today(),
            )
            source_hash = period_context.source_hash
            system_prompt, user_prompt = build_period_prompt(period_context.context)
            completion = self.llm_client.complete_json(
                system_prompt=system_prompt, user_prompt=user_prompt
            )
            review = parse_period_review(completion.payload)
        except Exception as exc:
            self._handle_failure(
                period,
                exc,
                stats,
                label=f"{period.period_type} coaching summary",
                failed_source_hash=source_hash,
            )
            return
        self.repository.mark_period_ready(
            period,
            summary=review.summary,
            recommendation=review.recommendation,
            source_hash=period_context.source_hash,
            is_final=period_context.is_final,
            model=completion.model,
            prompt_version=PROMPT_VERSION,
        )
        stats.period_summaries_generated += 1
        logger.info(
            "Generated period coaching summary.",
            extra={
                "user.id": period.user_id,
                "coaching.period_type": period.period_type,
                "coaching.period_start": period.period_start.isoformat(),
            },
        )

    def _handle_failure(
        self,
        row,
        exc: Exception,
        stats: CoachingRunStats,
        *,
        label: str,
        failed_source_hash: str | None = None,
    ) -> None:
        if isinstance(exc, LlmRateLimitedError):
            # Quota exhaustion is not the row's fault, so it does not count as an attempt.
            self.repository.release_for_retry(
                row,
                error_message=str(exc),
                delay_seconds=exc.retry_after_seconds,
                attempt_count=row.attempt_count,
            )
            logger.warning(
                "LLM rate limit reached; pausing AI coaching generation.",
                extra={"user.id": row.user_id, "retry_after_seconds": exc.retry_after_seconds},
            )
            raise _StopRun() from exc

        stats.failures += 1
        attempt_count = row.attempt_count + 1
        if attempt_count >= MAX_ATTEMPTS:
            # Recording the failed inputs stops the planner from re-queueing them until they change.
            self.repository.mark_failed(
                row,
                error_message=str(exc),
                attempt_count=attempt_count,
                source_hash=failed_source_hash,
            )
            logger.error(
                f"Giving up on {label} after repeated failures.",
                exc_info=(type(exc), exc, exc.__traceback__),
                extra={"user.id": row.user_id},
            )
            return
        delay_seconds = min(MAX_RETRY_DELAY_SECONDS, 300 * 2 ** (attempt_count - 1))
        self.repository.release_for_retry(
            row, error_message=str(exc), delay_seconds=delay_seconds, attempt_count=attempt_count
        )
        logger.warning(
            f"Failed to generate {label}; it will be retried.",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"user.id": row.user_id, "retry_after_seconds": delay_seconds},
        )
