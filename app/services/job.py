from datetime import datetime, UTC

from app.models.user import User
from app.repositories.job_history import JobHistoryRepository
from app.tasks.celery_app import celery_app
from app.tasks.scan_tasks import (
    detect_duplicates_task,
    scan_full_task,
    scan_incremental_task,
    verify_integrity_task,
)
from app.tasks.artwork_tasks import validate_artwork_task
from app.tasks.metadata_tasks import refresh_metadata_task
from app.utils.enums import JobStatus, JobType
from sqlalchemy.orm import Session


class JobService:
    def __init__(self) -> None:
        self.repo = JobHistoryRepository()

    def list_jobs(
        self,
        db: Session,
        job_type: JobType | None = None,
        status: JobStatus | None = None,
        offset: int = 0,
        limit: int = 100,
    ):
        return self.repo.list_items(db, job_type=job_type, status=status, offset=offset, limit=limit)

    def get_job(self, db: Session, job_id: str):
        return self.repo.get(db, job_id)

    def start_job(self, db: Session, user: User | None, job_type: JobType):
        job = self.repo.create(db, {
            "job_type": job_type,
            "status": JobStatus.PENDING,
            "progress": 0,
            "details": "Queued",
            "user_id": user.id if user else None,
        })
        task = self._select_task(job_type).apply_async(args=[job.id])
        job.task_id = task.id
        job.details = f"Queued task {task.id}"
        return self.repo.update(db, job, {"task_id": task.id, "details": job.details})

    def _select_task(self, job_type: JobType):
        return {
            JobType.LIBRARY_SCAN: scan_full_task,
            JobType.INCREMENTAL_SCAN: scan_incremental_task,
            JobType.METADATA_REFRESH: refresh_metadata_task,
            JobType.ARTWORK_REFRESH: validate_artwork_task,
            JobType.DUPLICATE_DETECTION: detect_duplicates_task,
            JobType.INTEGRITY_VERIFICATION: verify_integrity_task,
        }[job_type]

    def cancel_job(self, db: Session, job_id: str):
        job = self.repo.get(db, job_id)
        if job is None:
            return None
        if job.status not in {JobStatus.PENDING, JobStatus.RUNNING}:
            return job
        if job.task_id:
            celery_app.control.revoke(job.task_id, terminate=True)
        job.status = JobStatus.CANCELED
        job.details = "Canceled"
        job.completed_at = datetime.now(UTC)
        return self.repo.update(db, job, {"status": job.status, "details": job.details, "completed_at": job.completed_at})

    def is_cancelled(self, db: Session, job_id: str,) -> bool:
        job = self.repo.get(db, job_id,)
        return (job is not None and job.status == JobStatus.CANCELED)