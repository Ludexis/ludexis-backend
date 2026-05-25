from datetime import datetime

from app.db.session import SessionLocal
from app.repositories.job_history import JobHistoryRepository
from app.services.artwork import ArtworkService
from app.tasks.celery_app import celery_app
from app.utils.enums import JobStatus, JobType


@celery_app.task(bind=True)
def validate_artwork_task(self, job_history_id: str) -> str:
    db = SessionLocal()
    job_repo = JobHistoryRepository()
    job = job_repo.get(db, job_history_id)
    if job is None:
        db.close()
        return "job not found"
    try:
        job.status = JobStatus.RUNNING
        job.details = "Artwork validation started"
        db.add(job)
        db.commit()

        artwork_service = ArtworkService()
        results = artwork_service.validate_all_artwork(db)

        job.status = JobStatus.SUCCESS
        job.progress = 100
        job.result = f"Artwork validation completed: {len(results)} entries checked"
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
