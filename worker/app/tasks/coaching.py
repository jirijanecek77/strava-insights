import logging
from contextlib import closing

from app.celery_app import celery_app
from app.config import settings
from app.db import SessionLocal
from app.repositories import CoachingRepository
from app.services.coaching.generator import CoachingGenerator, CoachingRunStats
from app.services.coaching.llm_client import GroqLlmClient
from app.services.planning.generator import PlanningGenerator
from app.services.planning.repository import PlanningRepository

logger = logging.getLogger(__name__)


def run_coaching_generation(
    *, user_id: int | None = None, batch_size: int | None = None
) -> CoachingRunStats:
    session = SessionLocal()
    try:
        with closing(GroqLlmClient()) as llm_client:
            return CoachingGenerator(
                repository=CoachingRepository(session),
                llm_client=llm_client,
                is_configured=llm_client.is_configured,
                batch_size=batch_size or settings.coaching_batch_size,
                planning_generator=PlanningGenerator(
                    repository=PlanningRepository(session), llm_client=llm_client
                ),
            ).run(user_id=user_id)
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
    }


def run_planning_generation(*, user_id: int):
    """Run only planning work, used by the explicit manual replan command."""
    with SessionLocal() as session, closing(GroqLlmClient()) as client:
        return PlanningGenerator(
            repository=PlanningRepository(session), llm_client=client
        ).run(user_id=user_id, budget=1)


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
