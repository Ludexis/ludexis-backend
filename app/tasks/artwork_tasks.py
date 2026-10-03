from app.services.artwork import ArtworkService
from app.tasks.celery_app import celery_app
from app.tasks.job_runner import JOB_TASK_OPTIONS, run_job


@celery_app.task(**JOB_TASK_OPTIONS)
def validate_artwork_task(self, job_history_id: str) -> str:
    # Validates every entry's artwork and re-downloads missing or corrupt assets for provider-matched entries.
    return run_job(
        self,
        job_history_id,
        "Artwork refresh",
        lambda db, report, job_id: ArtworkService().validate_and_redownload_artwork(db),
    )

