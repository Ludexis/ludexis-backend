import time
from datetime import datetime

from celery import Celery
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.job_history import JobHistory
from app.repositories.job_history import JobHistoryRepository
from app.utils.enums import JobStatus

celery_app = Celery(
    "ludexis",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(bind=True)
def run_job(self, job_history_id: str) -> str:
    db = SessionLocal()
    try:
        repo = JobHistoryRepository()
        job = repo.get(db, job_history_id)
        if job is None:
            return "job not found"

        job.status = JobStatus.RUNNING
        job.progress = 0
        job.details = "Job started"
        db.add(job)
        db.commit()

        total_steps = 5
        for step in range(1, total_steps + 1):
            if self.request.called_directly or self.request.is_eager:
                pass

            job.progress = int(step / total_steps * 100)
            job.details = f"Running {job.job_type} ({job.progress}%)"
            db.add(job)
            db.commit()
            time.sleep(1)

        job.status = JobStatus.SUCCESS
        job.progress = 100
        job.result = f"{job.job_type} completed successfully"
        job.details = job.result
        job.completed_at = datetime.utcnow()
        db.add(job)
        db.commit()
        return job.result
    except Exception as exc:
        job = repo.get(db, job_history_id)
        if job:
            job.status = JobStatus.FAILED
            job.details = str(exc)
            job.result = str(exc)
            job.completed_at = datetime.utcnow()
            db.add(job)
            db.commit()
        raise
    finally:
        db.close()


# Import scan task definitions to make them available to Celery workers.
import app.tasks.scan_tasks  # noqa: F401
