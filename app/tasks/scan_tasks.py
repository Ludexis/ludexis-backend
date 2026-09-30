from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.repositories.job_history import JobHistoryRepository
from app.services.scanner import ScannerService
from app.tasks.celery_app import celery_app
from app.tasks.job_runner import JOB_TASK_OPTIONS, run_job
from app.utils.enums import JobType

logger = get_logger(__name__)


def _queue_enrichment(db: Session, scan_job_id: str, stats: dict) -> dict:
    # New entries go straight into metadata matching and artwork download as a separate, visible job.
    if stats.get("cancelled") or not stats["created_ids"]:
        return stats
    from app.services.job import JobService

    scan_job = JobHistoryRepository().get(db, scan_job_id)
    enrichment_job = JobService().start_job(
        db,
        scan_job.user if scan_job else None,
        JobType.METADATA_REFRESH,
        details=f"Enrich {len(stats['created_ids'])} new entries",
        task_kwargs={"entry_ids": stats["created_ids"]},
    )
    logger.info(
        "Enrichment queued after scan",
        extra={
            "job_id": scan_job_id,
            "enrichment_job_id": enrichment_job.id,
            "entries": len(stats["created_ids"]),
        },
    )
    stats["enrichment_job_id"] = enrichment_job.id
    return stats


@celery_app.task(**JOB_TASK_OPTIONS)
def scan_full_task(self, job_history_id: str) -> str:
    return run_job(
        self,
        job_history_id,
        "Full scan",
        lambda db, report, job_id: _queue_enrichment(
            db, job_id, ScannerService().scan_full(db, job_id=job_id, on_progress=report)
        ),
    )


@celery_app.task(**JOB_TASK_OPTIONS)
def scan_incremental_task(self, job_history_id: str) -> str:
    return run_job(
        self,
        job_history_id,
        "Incremental scan",
        lambda db, report, job_id: _queue_enrichment(
            db, job_id, ScannerService().scan_incremental(db, job_id=job_id, on_progress=report)
        ),
    )


@celery_app.task(**JOB_TASK_OPTIONS)
def verify_integrity_task(self, job_history_id: str) -> str:
    return run_job(
        self,
        job_history_id,
        "Integrity verification",
        lambda db, report, job_id: ScannerService().verify_archives(db),
    )


@celery_app.task(**JOB_TASK_OPTIONS)
def detect_duplicates_task(self, job_history_id: str) -> str:
    return run_job(
        self,
        job_history_id,
        "Duplicate detection",
        lambda db, report, job_id: {"duplicate_groups": len(ScannerService().find_duplicates(db))},
    )
