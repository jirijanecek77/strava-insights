import logging
from contextlib import closing
from datetime import UTC, datetime

from app.celery_app import celery_app
from app.config import settings
from app.db import SessionLocal
from app.infrastructure.ai.langchain_groq import LangChainGroqProvider
from app.infrastructure.ai.langgraph_workflow import AiWorkflow, RunStats
from app.services.ai.attempts import DatabaseAttemptRecorder
from app.services.ai.repository import AiWorkRepository
from app.services.coaching.period_planner import PeriodPlanner
from app.services.planning.stats import PlanningRunStats

logger = logging.getLogger(__name__)


def run_coaching_generation(
    *, user_id: int | None = None, batch_size: int | None = None
) -> RunStats:
    session = SessionLocal()
    try:
        repository = AiWorkRepository(session)
        recorder = DatabaseAttemptRecorder(session, repository.owns)
        with closing(LangChainGroqProvider(recorder)) as provider:
            planner = PeriodPlanner(
                repository.coaching,
                repository.snapshots.contexts,
                lambda: datetime.now(UTC).date(),
            )
            return AiWorkflow(repository, provider, planner).run(
                user_id=user_id,
                call_budget=(
                    settings.coaching_batch_size if batch_size is None else batch_size
                ),
            )
    finally:
        session.close()


@celery_app.task(name="app.tasks.coaching.generate_coaching")
def generate_coaching(*, user_id: int | None = None) -> dict:
    stats = run_coaching_generation(user_id=user_id)
    return {
        "activity_notes_generated": stats.activity_notes_generated,
        "period_summaries_generated": stats.period_summaries_generated,
        "failures": stats.failures,
        "rate_limited": stats.rate_limited,
        "training_plans_generated": stats.training_plans_generated,
        "skipped_reason": stats.skipped_reason,
        "provider_calls": stats.provider_calls,
        "work_items": stats.work_items,
        "obsolete": stats.obsolete,
    }


def run_planning_generation(*, user_id: int):
    """Run only planning work, used by the explicit manual replan command."""
    with SessionLocal() as session:
        repository = AiWorkRepository(session)
        recorder = DatabaseAttemptRecorder(session, repository.owns)
        with closing(LangChainGroqProvider(recorder)) as provider:
            stats = AiWorkflow(repository, provider, None).run(
                user_id=user_id, call_budget=1, planning_only=True
            )
            return PlanningRunStats(
                generated=stats.training_plans_generated,
                calls=stats.provider_calls,
                failures=stats.failures,
                rate_limited=stats.rate_limited,
                insufficient_data=stats.insufficient_data,
                skipped_reason=stats.skipped_reason,
            )


def trigger_coaching_generation(user_id: int) -> None:
    """Start generation right after a sync; the periodic beat run picks up anything this misses."""
    try:
        generate_coaching.delay(user_id=user_id)
    except Exception:
        logger.warning(
            "Could not enqueue AI coaching generation; the scheduled run will pick it up.",
            exc_info=True,
            extra={"user.id": user_id},
        )
