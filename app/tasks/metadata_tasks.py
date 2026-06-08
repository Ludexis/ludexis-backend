from datetime import datetime, UTC

from app.db.session import SessionLocal
from app.repositories.job_history import JobHistoryRepository
from app.services.metadata import MetadataService
from app.tasks.celery_app import celery_app
from app.utils.enums import JobStatus, JobType
from app.models.job_history import JobHistory

@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={
        "max_retries": 5,
    },
)
def refresh_metadata_task(self, job_history_id: str,) -> str:
    db = SessionLocal()
    job_repo = JobHistoryRepository()

    try:
        job = job_repo.get(db, job_history_id,)
        if job is None:
            return "job not found"

        job.status = (JobStatus.RUNNING)
        job.details = ("Metadata refresh started")

        db.add(job)
        db.commit()

        metadata_service = (MetadataService())
        stats = (metadata_service.refresh_all(db, job.id,))        
        if stats.get("cancelled"):
            job.status = (JobStatus.CANCELED)
            job.result = ("Metadata refresh cancelled")
        else:
            job.status = (JobStatus.SUCCESS)
            job.result = (f"Metadata refresh completed: {stats}")
        job.progress = 100
        job.details = (job.result)
        job.completed_at = (datetime.now(UTC))

        db.add(job)
        db.commit()

        return job.result

    except Exception as exc:
        if job is not None:
            job.status = (JobStatus.FAILED)
            job.details = str(exc)
            job.result = str(exc)
            job.completed_at = (datetime.now(UTC))

            db.add(job)
            db.commit()

        raise

    finally:
        db.close()


@celery_app.task
def scheduled_metadata_refresh_task() -> str:
    db = SessionLocal()
    existing = (db.query(JobHistory).filter(
            JobHistory.job_type == JobType.METADATA_REFRESH,
            JobHistory.status.in_(
                [
                    JobStatus.PENDING,
                    JobStatus.RUNNING,
                ]
            ),
        )
        .first()
    )

    if existing:
        return (f"metadata refresh already active: "f"{existing.id}")

    try:
        job = JobHistory(
            job_type=(JobType.METADATA_REFRESH),
            status=(JobStatus.PENDING),
            details=("Scheduled metadata refresh"),
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        task = (refresh_metadata_task.delay(job.id))
        job.task_id = task.id

        db.add(job)
        db.commit()

        return task.id

    finally:
        db.close()
