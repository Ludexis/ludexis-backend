from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.core.auth import PermissionName
from app.db.session import get_db
from app.schemas.job_history import JobHistoryRead
from app.schemas.scan import ScanStatus
from app.services.job import JobService
from app.repositories.job_history import JobHistoryRepository
from app.utils.enums import JobType, JobStatus

router = APIRouter(prefix="/scan", tags=["scan"])
job_service = JobService()
job_repo = JobHistoryRepository()


@router.post("/full", response_model=JobHistoryRead, status_code=status.HTTP_201_CREATED)
def start_full_scan(
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    return job_service.start_job(db, current_user, JobType.LIBRARY_SCAN)


@router.post("/incremental", response_model=JobHistoryRead, status_code=status.HTTP_201_CREATED)
def start_incremental_scan(
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    return job_service.start_job(db, current_user, JobType.INCREMENTAL_SCAN)


@router.get("/status", response_model=ScanStatus)
def read_scan_status(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    jobs = job_repo.list(db)
    scan_jobs = [job for job in jobs if job.job_type in {JobType.LIBRARY_SCAN, JobType.INCREMENTAL_SCAN}]
    counts = {
        "pending": sum(1 for job in scan_jobs if job.status == JobStatus.PENDING),
        "running": sum(1 for job in scan_jobs if job.status == JobStatus.RUNNING),
        "success": sum(1 for job in scan_jobs if job.status == JobStatus.SUCCESS),
        "failed": sum(1 for job in scan_jobs if job.status == JobStatus.FAILED),
        "canceled": sum(1 for job in scan_jobs if job.status == JobStatus.CANCELED),
    }
    counts["total"] = len(scan_jobs)
    return ScanStatus(**counts)
