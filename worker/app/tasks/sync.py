import logging

from app.celery_app import celery_app
from app.db import SessionLocal
from app.logging import reset_log_user_name, set_log_user_name
from app.repositories import SyncJobRepository, UserRepository
from app.services.sync_scheduler import DailyIncrementalSyncScheduler
from app.services.sync_import import FullImportService, IncrementalSyncService


logger = logging.getLogger(__name__)


def _set_task_log_user_name(session, user_id: int):
    user = UserRepository(session).get_by_id(user_id)
    return set_log_user_name(None if user is None else user.display_name)


@celery_app.task(name="app.tasks.sync.run_full_import")
def run_full_import(*, sync_job_id: int, user_id: int) -> None:
    session = SessionLocal()
    log_user_token = _set_task_log_user_name(session, user_id)
    sync_jobs = SyncJobRepository(session)
    try:
        logger.info("Running full import task.", extra={"sync_job.id": sync_job_id, "user.id": user_id})
        FullImportService(session).run(sync_job_id=sync_job_id, user_id=user_id)
    except Exception as exc:
        session.rollback()
        sync_job = sync_jobs.get(sync_job_id, user_id)
        if sync_job is not None:
            sync_jobs.fail(sync_job, error_message=str(exc))
            session.commit()
        logger.error(
            "Full import task failed.",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"sync_job.id": sync_job_id, "user.id": user_id},
        )
        raise
    finally:
        reset_log_user_name(log_user_token)
        session.close()


@celery_app.task(name="app.tasks.sync.run_incremental_sync")
def run_incremental_sync(*, sync_job_id: int, user_id: int) -> None:
    session = SessionLocal()
    log_user_token = _set_task_log_user_name(session, user_id)
    sync_jobs = SyncJobRepository(session)
    try:
        logger.info("Running incremental sync task.", extra={"sync_job.id": sync_job_id, "user.id": user_id})
        IncrementalSyncService(session).run(sync_job_id=sync_job_id, user_id=user_id)
    except Exception as exc:
        session.rollback()
        sync_job = sync_jobs.get(sync_job_id, user_id)
        if sync_job is not None:
            sync_jobs.fail(sync_job, error_message=str(exc))
            session.commit()
        logger.error(
            "Incremental sync task failed.",
            exc_info=(type(exc), exc, exc.__traceback__),
            extra={"sync_job.id": sync_job_id, "user.id": user_id},
        )
        raise
    finally:
        reset_log_user_name(log_user_token)
        session.close()


@celery_app.task(name="app.tasks.sync.schedule_daily_incremental_syncs")
def schedule_daily_incremental_syncs() -> int:
    session = SessionLocal()
    try:
        logger.info("Running daily incremental sync scheduler.")
        scheduled_jobs = DailyIncrementalSyncScheduler(session).run()
        session.commit()
        logger.info("Finished daily incremental sync scheduler.", extra={"scheduled_jobs": scheduled_jobs})
        return scheduled_jobs
    finally:
        session.close()
