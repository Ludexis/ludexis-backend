from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.core.auth import PermissionName
from app.db.session import get_db
from app.schemas.job_history import JobHistoryRead
from app.schemas.scan import ScanStatus
from app.services.audit_log import AuditLogService
from app.services.job import JobService
from app.repositories.job_history import JobHistoryRepository
from app.utils.audit_actions import AuditAction
from app.utils.enums import JobType, JobStatus

router = APIRouter(prefix="/scan", tags=["scan"])
job_service = JobService()
job_repo = JobHistoryRepository()
audit_log_service = AuditLogService()


@router.post(
    "/full",
    response_model=JobHistoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start full scan",
    description="Queue a full library scan job.",
    response_description="Scan job started.",
)
def start_full_scan(
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    job = job_service.start_job(db, current_user, JobType.LIBRARY_SCAN)
    audit_log_service.log(
        db,
        action=AuditAction.RUN_FULL_SCAN,
        entity="Scan",
        user_id=current_user.id,
        details="Triggered full library scan",
    )
    return job


@router.post(
    "/incremental",
    response_model=JobHistoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Start incremental scan",
    description="Queue an incremental library scan job.",
    response_description="Scan job started.",
)
def start_incremental_scan(
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    job = job_service.start_job(db, current_user, JobType.INCREMENTAL_SCAN)
    audit_log_service.log(
        db,
        action=AuditAction.RUN_INCREMENTAL_SCAN,
        entity="Scan",
        user_id=current_user.id,
        details="Triggered incremental library scan",
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
