from datetime import datetime, UTC
from typing import Callable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.repositories.job_history import JobHistoryRepository
from app.services.scanner import ProgressCallback
from app.utils.enums import JobStatus

# Shared Celery options for every job task: retry on any error with exponential backoff.
JOB_TASK_OPTIONS = {
    "bind": True,
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_backoff_max": settings.JOB_RETRY_BACKOFF_MAX,
    "retry_kwargs": {
        "max_retries": settings.JOB_MAX_RETRIES,
    },
}

# Receives the session, a progress reporter and the job id; returns a stats dict.
JobWork = Callable[[Session, ProgressCallback, str], dict]


def run_job(task, job_history_id: str, label: str, work: JobWork) -> str:
    """Runs one job_history row through RUNNING -> SUCCESS | CANCELED | FAILED.

    Celery retries re-run the same row, so the attempt number is stored in retry_count.
    """
    db = SessionLocal()
    job = None
    try:
        job = JobHistoryRepository().get(db, job_history_id)
        if job is None:
            return "job not found"

        job.status = JobStatus.RUNNING
        job.details = f"{label} started"
        job.progress = 0
        job.retry_count = task.request.retries or 0
        job.completed_at = None
        db.commit()

        def report(done: int, total: int) -> None:
            percent = int(done * 100 / total) if total else 100
            if percent != job.progress:
                job.progress = percent
                db.commit()

        stats = work(db, report, job.id)

        if stats.get("cancelled"):
            job.status = JobStatus.CANCELED
            job.result = f"{label} cancelled"
        else:
            job.status = JobStatus.SUCCESS
            job.progress = 100
            job.result = f"{label} completed: {summarize(stats)}"
        job.details = job.result
        job.completed_at = datetime.now(UTC)
        db.commit()
        return job.result
    except Exception as exc:
        db.rollback()
        if job is not None:
            job.status = JobStatus.FAILED
            job.details = str(exc)
            job.result = str(exc)
            job.completed_at = datetime.now(UTC)
            db.commit()
        raise
    finally:
        db.close()


def summarize(stats: dict) -> dict:
    return {
        key: value
        for key, value in stats.items()
        if key != "cancelled" and not isinstance(value, (list, dict))
    }
