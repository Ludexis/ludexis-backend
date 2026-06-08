from datetime import datetime, UTC

from app.db.session import SessionLocal
from app.repositories.job_history import JobHistoryRepository
from app.services.scanner import ScannerService
from app.tasks.celery_app import celery_app
from app.utils.enums import JobStatus, JobType


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={
        "max_retries": 3,
    },
)
def scan_full_task(self, job_history_id: str) -> str:
    db = SessionLocal()
    try:
        job_repo = JobHistoryRepository()
        job = job_repo.get(db, job_history_id)
        if job is None:
            return "job not found"

        job.status = JobStatus.RUNNING
        job.details = "Full scan started"
        db.add(job)
        db.commit()

        scanner = ScannerService()
        stats = scanner.scan_full(db, job_id=job.id,)

        if stats.get("cancelled"):
            job.status = (JobStatus.CANCELED)
            job.result = ("Full scan cancelled")
        else:
            job.status = (JobStatus.SUCCESS)
            job.result = (f"Full scan completed: {stats}")

        job.progress = 100
        job.details = job.result
        job.completed_at = (datetime.now(UTC))

        db.add(job)
        db.commit()
        return job.result
    except Exception as exc:
        if job is not None:
            job.status = JobStatus.FAILED
            job.details = str(exc)
            job.result = str(exc)
            job.completed_at = datetime.now(UTC)
            db.add(job)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={
        "max_retries": 3,
    },
)
def scan_incremental_task(self, job_history_id: str) -> str:
    db = SessionLocal()
    try:
        job_repo = JobHistoryRepository()
        job = job_repo.get(db, job_history_id)
        if job is None:
            return "job not found"

        job.status = JobStatus.RUNNING
        job.details = "Incremental scan started"

        db.add(job)
        db.commit()

        scanner = ScannerService()
        stats = scanner.scan_incremental(db, job_id=job.id,)

        if stats.get("cancelled"):
            job.status = (JobStatus.CANCELED)
            job.result = ("Incremental scan cancelled")
        else:
            job.status = (JobStatus.SUCCESS)
            job.result = (f"Incremental scan completed: {stats}")

        job.progress = 100
        job.details = job.result
        job.completed_at = (datetime.now(UTC))
        
        db.add(job)
        db.commit()
        return job.result
    except Exception as exc:
        if job is not None:
            job.status = JobStatus.FAILED
            job.details = str(exc)
            job.result = str(exc)
            job.completed_at = datetime.now(UTC)
            db.add(job)
            db.commit()
        raise
    finally:
        db.close()
