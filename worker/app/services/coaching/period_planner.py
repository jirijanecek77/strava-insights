"""Local period invalidation policy shared by workflow entry points."""

from datetime import date, timedelta

from app.services.coaching.context_builder import period_start_for
from app.services.coaching.evidence import fingerprint
from app.services.coaching.prompts import PROMPT_VERSION

PERIOD_PLANNING_WINDOW_DAYS = 70
PERIOD_TYPES = ("week", "month")


class PeriodPlanner:
    def __init__(self, repository, context_builder, today):
        self.repository = repository
        self.context_builder = context_builder
        self.today = today

    def plan(self, *, user_id: int | None) -> list[tuple[int, str, date]]:
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
                },
                key=lambda key: (key[0] != "week", key[1]),
            )
            for period_type, period_start in period_keys:
                period_context = self.context_builder.build_period_context(
                    user_id=candidate_user_id,
                    period_type=period_type,
                    period_start=period_start,
                    today=today,
                )
                # Wait until every activity note in the period is done, so the review sees all summaries.
                if (
                    period_context.has_pending_notes
                    or not period_context.has_ready_notes
                ):
                    continue
                period = self.repository.get_or_create_period(
                    user_id=candidate_user_id,
                    period_type=period_type,
                    period_start=period_start,
                )
                # A deployment alone must not replace historical ready text. Explicit regeneration
                # or a newly generated activity note can upgrade it; unfinished reviews still finalize.
                legacy_ready = (
                    period.status == "ready"
                    and getattr(period, "prompt_version", PROMPT_VERSION)
                    != PROMPT_VERSION
                )
                if (
                    period.period_type == "week"
                    and period.status == "ready"
                    and not (getattr(period, "metrics", None) or {}).get("hierarchy")
                    and period_context.metrics is not None
                ):
                    # Upgrade the numeric handoff from cached child results only, retaining
                    # legacy prose. This never reads original streams or calls the model.
                    period.metrics = period_context.metrics
                    self.repository.commit()
                if legacy_ready and (period.is_final or not period_context.is_final):
                    if hasattr(
                        self.repository, "has_new_coaching_notes"
                    ) and not self.repository.has_new_coaching_notes(period):
                        self.repository.commit()
                        continue
                if (
                    period.status == "ready"
                    and period.is_final
                    and not legacy_ready
                    and (getattr(period, "metrics", None) or {}).get("hierarchy")
                    and period_context.metrics is not None
                    and fingerprint(period.metrics["hierarchy"]["days"])
                    == fingerprint(period_context.metrics["hierarchy"]["days"])
                ):
                    # December changes to a boundary week must not rewrite a closed November.
                    self.repository.commit()
                    continue
                already_queued = period.status in {"pending", "generating"}
                inputs_unchanged = period.source_hash == period_context.source_hash
                needs_final_review = period_context.is_final and not period.is_final
                if already_queued or (
                    inputs_unchanged
                    and (period.status == "failed" or not needs_final_review)
                ):
                    self.repository.commit()
                    continue
                self.repository.mark_period_pending(period)
                planned.append((candidate_user_id, period_type, period_start))
        return planned
