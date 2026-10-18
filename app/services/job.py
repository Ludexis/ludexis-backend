from datetime import datetime, timedelta, UTC

from app.models.edge_device import EdgeDevice
from app.models.job_history import JobHistory
from app.models.library import Library
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


# A job still RUNNING this long after it started, or never picked up from the queue, is treated as lost.
STALE_RUNNING_AFTER = timedelta(hours=12)
STALE_PENDING_AFTER = timedelta(hours=24)
# An edge device may stay switched off for days; its waiting jobs are kept for a week. One that stops checking in
# while it runs a job has lost it.
EDGE_PENDING_EXPIRES_AFTER = timedelta(days=7)
EDGE_LOST_AFTER = timedelta(hours=1)
SCAN_JOBS = {JobType.LIBRARY_SCAN, JobType.INCREMENTAL_SCAN}


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

    def start_job(self, db: Session, user: User | None, job_type: JobType, details: str | None = None, task_kwargs: dict | None = None):
        library_id = (task_kwargs or {}).get("library_id")
        library = db.get(Library, library_id) if library_id else None
        # A library on an edge device is scanned there; the job waits until that device checks in.
        if library is not None and library.edge_id:
            return self.queue_edge_scan(db, user, job_type, library)
        job = self.repo.create(db, {
            "job_type": job_type,
            "status": JobStatus.PENDING,
            "progress": 0,
            "details": details or "Queued",
            "user_id": user.id if user else None,
            "library_id": library_id if job_type in SCAN_JOBS else None,
        })
        task = self._select_task(job_type).apply_async(args=[job.id], kwargs=task_kwargs or {})
        job = self.repo.update(db, job, {"task_id": task.id, "details": details or f"Queued task {task.id}"})
        # A scan of everything covers the libraries on edge devices too.
        if job_type in SCAN_JOBS and library is None:
            for edge_library in db.query(Library).filter(Library.edge_id.is_not(None), Library.enabled.is_(True), Library.deleted_at.is_(None)):
                self.queue_edge_scan(db, user, job_type, edge_library)
        return job

    def queue_edge_scan(self, db: Session, user: User | None, job_type: JobType, library: Library, details: str | None = None) -> JobHistory:
        # One waiting or running scan per library is enough, however often a scan is asked for while the device is away.
        waiting = (
            db.query(JobHistory)
            .filter(JobHistory.library_id == library.id, JobHistory.edge_id.is_not(None), JobHistory.status.in_([JobStatus.PENDING, JobStatus.RUNNING]))
            .first()
        )
        if waiting is not None:
            return waiting
        return self.repo.create(db, {
            "job_type": job_type,
            "status": JobStatus.PENDING,
            "progress": 0,
            "details": details or f"Waiting for {library.edge.name} to scan {library.name}",
            "user_id": user.id if user else None,
            "library_id": library.id,
            "edge_id": library.edge_id,
        })

    def active_job(self, db: Session, job_type: JobType):
        return (
            db.query(JobHistory)
            .filter(
                JobHistory.job_type == job_type,
                JobHistory.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
                # A device that is switched off must not hold up the server's own jobs.
                JobHistory.edge_id.is_(None),
            )
            .first()
        )

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

    def fail_stale_jobs(self, db: Session, worker_restarted: bool = False) -> int:
        """Mark jobs whose worker died as FAILED so they stop showing as running and block nothing."""
        now = datetime.now(UTC)
        stale = []
        for job in db.query(JobHistory).filter(JobHistory.status.in_([JobStatus.PENDING, JobStatus.RUNNING])):
            age = now - job.started_at
            # An edge job belongs to its device until the server's worker takes its report (task_id set).
            if job.edge_id and not job.task_id:
                edge = db.get(EdgeDevice, job.edge_id)
                if job.status == JobStatus.PENDING and age > EDGE_PENDING_EXPIRES_AFTER:
                    stale.append((job, f"{edge.name} did not check in within {EDGE_PENDING_EXPIRES_AFTER.days} days"))
                elif job.status == JobStatus.RUNNING and (edge.last_seen_at is None or now - edge.last_seen_at > EDGE_LOST_AFTER):
                    stale.append((job, f"{edge.name} stopped checking in while it ran the job"))
                continue
            if job.status == JobStatus.RUNNING and (worker_restarted or age > STALE_RUNNING_AFTER):
                # assumes one worker; with several, a restart of one would fail the others' jobs.
                stale.append((job, "Worker stopped while the job was running"))
            elif job.status == JobStatus.PENDING and age > STALE_PENDING_AFTER:
                stale.append((job, "Job was never picked up by a worker"))
        for job, reason in stale:
            job.status = JobStatus.FAILED
            job.details = reason
            job.result = reason
            job.completed_at = now
        db.commit()
        return len(stale)

    def is_cancelled(self, db: Session, job_id: str,) -> bool:
        job = self.repo.get(db, job_id,)
        return (job is not None and job.status == JobStatus.CANCELED)