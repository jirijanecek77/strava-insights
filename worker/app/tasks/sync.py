from app.celery_app import celery_app
from app.db import SessionLocal
from app.repositories import SyncJobRepository
from app.services.sync_scheduler import DailyIncrementalSyncScheduler
from app.services.sync_import import FullImportService, IncrementalSyncService


@celery_app.task(name="app.tasks.sync.run_full_import")
def run_full_import(*, sync_job_id: int, user_id: int) -> None:
    session = SessionLocal()
    sync_jobs = SyncJobRepository(session)
    try:
        FullImportService(session).run(sync_job_id=sync_job_id, user_id=user_id)
    except Exception as exc:
        session.rollback()
        sync_job = sync_jobs.get(sync_job_id, user_id)
        if sync_job is not None:
            sync_jobs.fail(sync_job, error_message=str(exc))
            session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="app.tasks.sync.run_incremental_sync")
def run_incremental_sync(*, sync_job_id: int, user_id: int) -> None:
    session = SessionLocal()
    sync_jobs = SyncJobRepository(session)
    try:
        IncrementalSyncService(session).run(sync_job_id=sync_job_id, user_id=user_id)
    except Exception as exc:
        session.rollback()
        sync_job = sync_jobs.get(sync_job_id, user_id)
        if sync_job is not None:
            sync_jobs.fail(sync_job, error_message=str(exc))
            session.commit()
        raise
    finally:
        session.close()


@celery_app.task(name="app.tasks.sync.schedule_daily_incremental_syncs")
def schedule_daily_incremental_syncs() -> int:
    session = SessionLocal()
    try:
        scheduled_jobs = DailyIncrementalSyncScheduler(session).run()
        session.commit()
        return scheduled_jobs
    finally:
        session.close()
