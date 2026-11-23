import subprocess
import sys
from pathlib import Path


def test_worker_console_logs_show_job_context_without_credentials_or_payloads():
    script = """
import logging
from app.logging import configure_logging, JobLogContext, set_log_job, reset_log_job, log_work_item
configure_logging(log_level="INFO", service_name="beat")
logger = logging.getLogger("app.test")
token = set_log_job(JobLogContext("job-12", "app.tasks.sync.run_full_import", 5))
with log_work_item(user_id=5, activity_id=42):
    logger.info("Finished phase.", extra={
        "duration_ms": 12.5, "imported_count": 3,
        "api_key": "secret", "task.kwargs": {"password": "private"},
        "llm.prompt": "private training data",
        "ai.prompt": "private training data", "ai.attempt_id": "attempt-42",
    })
reset_log_job(token)
logger.info("Unscoped job.")
"""
    output = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "job-12" in output and "run_full_import" in output
    assert '"duration_ms":12.5' in output and '"imported_count":3' in output
    assert "secret" not in output and "private" not in output
    assert "[beat]" in output and '"activity.id":42' in output
    assert '"ai.attempt_id":"attempt-42"' in output
    assert "job-12" not in output.splitlines()[-1]
    assert "activity.id" not in output.splitlines()[-1]
