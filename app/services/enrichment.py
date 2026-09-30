from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.job_history import JobHistory
from app.services.artwork import ArtworkService
from app.services.metadata import MetadataService
from app.services.scanner import ProgressCallback
from app.utils.enums import JobStatus, MetadataStatus

logger = get_logger(__name__)


class EnrichmentService:
    """Matches archive entries to provider metadata and downloads artwork for the matched ones."""

    def __init__(self, metadata_service: MetadataService | None = None, artwork_service: ArtworkService | None = None) -> None:
        self.metadata_service = metadata_service or MetadataService()
        self.artwork_service = artwork_service or ArtworkService(self.metadata_service)

    def enrich(self, db: Session, entry_ids: list[str] | None = None, job_id: str | None = None, on_progress: ProgressCallback | None = None,) -> dict:
        entries = self.metadata_service.enrichment_candidates(db, entry_ids)
        stats = {
            "processed": 0,
            "matched": 0,
            "unmatched": 0,
            "artwork_downloaded": 0,
            "errors": 0,
            "cancelled": False,
        }
        for index, entry in enumerate(entries, start=1):
            if job_id and self._job_cancelled(db, job_id):
                stats["cancelled"] = True
                return stats
            try:
                self.metadata_service.enrich_archive(db, entry)
                if entry.metadata_source_code and entry.metadata_status != MetadataStatus.UNMATCHED:
                    stats["matched"] += 1
                    stats["artwork_downloaded"] += self.artwork_service.fill_missing_artwork(db, entry)
                else:
                    stats["unmatched"] += 1
            except Exception:
                # A provider outage for one entry should not stop the rest of the batch.
                db.rollback()
                stats["errors"] += 1
                logger.exception(
                    "Entry enrichment failed",
                    extra={
                        "archive_id": entry.id,
                        "title": entry.title,
                    },
                )
            stats["processed"] += 1
            if on_progress:
                on_progress(index, len(entries))
        return stats

    def _job_cancelled(self, db: Session, job_id: str) -> bool:
        status = db.query(JobHistory.status).filter(JobHistory.id == job_id).scalar()
        return status == JobStatus.CANCELED
