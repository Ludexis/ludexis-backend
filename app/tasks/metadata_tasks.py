from app.db.session import SessionLocal
from app.services.enrichment import EnrichmentService
from app.tasks.celery_app import celery_app
from app.tasks.job_runner import JOB_TASK_OPTIONS, run_job
from app.utils.enums import JobType


@celery_app.task(**JOB_TASK_OPTIONS)
def refresh_metadata_task(self, job_history_id: str, entry_ids: list[str] | None = None) -> str:
    # Without entry_ids: refresh matched entries and match entries never attempted.
    return run_job(
        self,
        job_history_id,
        "Metadata refresh",
        lambda db, report, job_id: EnrichmentService().enrich(db, entry_ids, job_id, report),
    )


@celery_app.task
def scheduled_metadata_refresh_task() -> str:
    from app.services.job import JobService

    db = SessionLocal()
    try:
        service = JobService()
        active = service.active_job(db, JobType.METADATA_REFRESH)
        if active:
            return f"metadata refresh already active: {active.id}"
        return service.start_job(db, None, JobType.METADATA_REFRESH, details="Scheduled metadata refresh").task_id
    finally:
        db.close()
