from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.core.auth import PermissionName
from app.db.session import get_db
from app.schemas.job_history import JobHistoryRead, JobHistoryCreate
from app.services.job import JobService
from app.utils.enums import JobStatus, JobType

router = APIRouter(prefix="/jobs", tags=["jobs"])
service = JobService()


@router.post("/start", response_model=JobHistoryRead, status_code=status.HTTP_201_CREATED)
def start_job(
    data: JobHistoryCreate,
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    job = service.start_job(db, current_user, data.job_type)
    if job is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not start job")
    return job


@router.post("/{job_id}/cancel", response_model=JobHistoryRead)
def cancel_job(
    job_id: str,
    current_user=Depends(require_permission(PermissionName.RUN_SCANS)),
    db: Session = Depends(get_db),
):
    job = service.cancel_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.get("/", response_model=list[JobHistoryRead])
def list_jobs(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    offset: int = 0,
    limit: int = 100,
):
    return service.list_jobs(db, job_type=job_type, status=status, offset=offset, limit=limit)


@router.get("/{job_id}", response_model=JobHistoryRead)
def read_job(
    job_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    job = service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
