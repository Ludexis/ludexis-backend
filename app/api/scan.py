from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.core.auth import PermissionName
from app.db.session import get_db
from app.schemas.job_history import JobHistoryRead
from app.schemas.scan import ScanStatus
from app.services.audit import AuditService
from app.services.job import JobService
from app.models.library import Library
from app.repositories.job_history import JobHistoryRepository
from app.repositories.library import LibraryRepository
from app.utils.audit_actions import AuditAction
from app.utils.enums import JobType, JobStatus

router = APIRouter(prefix="/scan", tags=["scan"])
job_service = JobService()
job_repo = JobHistoryRepository()
audit_log_service = AuditService()
library_repo = LibraryRepository()


def _library(db: Session, library_id: str | None) -> Library | None:
    if library_id is None:
        return None
    library = library_repo.get_active(db, library_id)
    if library is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    return library


@router.post(
    "/full",
    response_model=JobHistoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start full scan",
    description="Queue a full scan job of every enabled library, or only of library_id.",
    response_description="Scan job started.",
)
def start_full_scan(
    library_id: str | None = None,
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    library = _library(db, library_id)
    job = job_service.start_job(
        db,
        current_user,
        JobType.LIBRARY_SCAN,
        details=f"Queued scan of {library.name}" if library else None,
        task_kwargs={"library_id": library.id} if library else None,
    )
    audit_log_service.log(
        db,
        action=AuditAction.RUN_FULL_SCAN,
        entity="Scan",
        user_id=current_user.id,
        details=f"Triggered full scan of library '{library.name}'" if library else "Triggered full library scan",
    )
    return job


@router.post(
    "/incremental",
    response_model=JobHistoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start incremental scan",
    description="Queue an incremental scan job of every enabled library, or only of library_id.",
    response_description="Scan job started.",
)
def start_incremental_scan(
    library_id: str | None = None,
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    library = _library(db, library_id)
    job = job_service.start_job(
        db,
        current_user,
        JobType.INCREMENTAL_SCAN,
        details=f"Queued scan of {library.name}" if library else None,
        task_kwargs={"library_id": library.id} if library else None,
    )
    audit_log_service.log(
        db,
        action=AuditAction.RUN_INCREMENTAL_SCAN,
        entity="Scan",
        user_id=current_user.id,
        details=f"Triggered incremental scan of library '{library.name}'" if library else "Triggered incremental library scan",
    )
    return job


@router.get(
    "/status",
    response_model=ScanStatus,
    summary="Get scan status",
    description="Return aggregated scan job status counts.",
    response_description="Scan status retrieved.",
)
def read_scan_status(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    counts_by_status = job_repo.count_by_status(db, [JobType.LIBRARY_SCAN, JobType.INCREMENTAL_SCAN])
    counts = {
        "pending": counts_by_status.get(JobStatus.PENDING, 0),
        "running": counts_by_status.get(JobStatus.RUNNING, 0),
        "success": counts_by_status.get(JobStatus.SUCCESS, 0),
        "failed": counts_by_status.get(JobStatus.FAILED, 0),
        "canceled": counts_by_status.get(JobStatus.CANCELED, 0),
    }
    counts["total"] = sum(counts.values())
    return ScanStatus(**counts)
