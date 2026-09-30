from app.db.session import SessionLocal
from app.services.artwork import ArtworkService
from app.tasks.celery_app import celery_app
from app.tasks.job_runner import JOB_TASK_OPTIONS, run_job
from app.utils.enums import JobType


@celery_app.task(**JOB_TASK_OPTIONS)
def validate_artwork_task(self, job_history_id: str) -> str:
    # Validates every entry's artwork and re-downloads missing or corrupt assets for provider-matched entries.
    return run_job(
        self,
        job_history_id,
        "Artwork refresh",
        lambda db, report, job_id: ArtworkService().validate_and_redownload_artwork(db),
    )


@celery_app.task
def scheduled_artwork_validation_task() -> str:
    from app.services.job import JobService

    db = SessionLocal()
    try:
        service = JobService()
        active = service.active_job(db, JobType.ARTWORK_REFRESH)
        if active:
            return f"artwork refresh already active: {active.id}"
        return service.start_job(db, None, JobType.ARTWORK_REFRESH, details="Scheduled artwork refresh").task_id
    finally:
        db.close()
