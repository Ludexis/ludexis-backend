from app.services.enrichment import EnrichmentService
from app.tasks.celery_app import celery_app
from app.tasks.job_runner import JOB_TASK_OPTIONS, run_job


@celery_app.task(**JOB_TASK_OPTIONS)
def refresh_metadata_task(self, job_history_id: str, entry_ids: list[str] | None = None) -> str:
    # Without entry_ids: refresh matched entries and match entries never attempted.
    return run_job(
        self,
        job_history_id,
        "Metadata refresh",
        lambda db, report, job_id: EnrichmentService().enrich(db, entry_ids, job_id, report),
    )

