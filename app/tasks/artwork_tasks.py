from app.services.artwork import ArtworkService
from app.tasks.celery_app import celery_app
from app.tasks.job_runner import JOB_TASK_OPTIONS, run_job


@celery_app.task(**JOB_TASK_OPTIONS)
def validate_artwork_task(self, job_history_id: str, mode: str = "validate", entry_ids: list[str] | None = None) -> str:
    # validate: check every entry's artwork and re-download missing or corrupt assets for provider-matched entries.
    # fill: download whatever artwork is missing for every entry.
    # replace: download fresh artwork for entry_ids, e.g. after a user identified them as a different game.
    if mode == "replace":
        return run_job(
            self,
            job_history_id,
            "Artwork replace",
            lambda db, report, job_id: ArtworkService().replace_entries_artwork(db, entry_ids or [], report),
        )
    if mode == "fill":
        return run_job(
            self,
            job_history_id,
            "Artwork download",
            lambda db, report, job_id: ArtworkService().auto_download_missing_artwork(db),
        )
    return run_job(
        self,
        job_history_id,
        "Artwork refresh",
        lambda db, report, job_id: ArtworkService().validate_and_redownload_artwork(db),
    )

