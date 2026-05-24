from datetime import datetime

from app.db.session import SessionLocal
from app.repositories.job_history import JobHistoryRepository
from app.services.scanner import ScannerService
from app.tasks.celery_app import celery_app
from app.utils.enums import JobStatus, JobType


@celery_app.task(bind=True)
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
        stats = scanner.scan_full(db)

        job.status = JobStatus.SUCCESS
        job.progress = 100
        job.result = f"Full scan completed: {stats}"
        job.details = job.result
        job.completed_at = datetime.utcnow()
        db.add(job)
        db.commit()
        return job.result
    except Exception as exc:
        if job is not None:
            job.status = JobStatus.FAILED
            job.details = str(exc)
            job.result = str(exc)
            job.completed_at = datetime.utcnow()
            db.add(job)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
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
        stats = scanner.scan_incremental(db)

        job.status = JobStatus.SUCCESS
        job.progress = 100
        job.result = f"Incremental scan completed: {stats}"
        job.details = job.result
        job.completed_at = datetime.utcnow()
        db.add(job)
        db.commit()
        return job.result
    except Exception as exc:
        if job is not None:
            job.status = JobStatus.FAILED
            job.details = str(exc)
            job.result = str(exc)
            job.completed_at = datetime.utcnow()
            db.add(job)
            db.commit()
        raise
    finally:
        db.close()
