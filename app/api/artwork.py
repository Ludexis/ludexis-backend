from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission, PermissionName
from app.db.session import get_db
from app.schemas.artwork import (
    ArtworkDeleteResponse,
    ArtworkMissingResponse,
    ArtworkReplaceResponse,
    ArtworkUploadResponse,
)
from app.services.artwork import ArtworkService
from app.services.audit import AuditService
from app.utils.audit_actions import AuditAction
from app.utils.artwork import ArtworkType
from app.utils.enums import JobType
from app.schemas.job_history import JobHistoryRead
from app.services.job import JobService

router = APIRouter(prefix="/artwork", tags=["artwork"])
service = ArtworkService()
audit_service = AuditService()


@router.post(
    "/upload",
    response_model=ArtworkUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload artwork",
    description="Upload artwork for an archive entry. Accepts multipart form data.",
    response_description="Artwork uploaded.",
)
def upload_artwork(
    archive_entry_id: str = Form(..., description="Archive entry ID", examples=["entry-uuid-1"]),
    artwork_type: ArtworkType = Form(..., description="Artwork type", examples=["cover"]),
    file: UploadFile = File(..., description="Artwork file"),
    caption: str | None = Form(None, description="Optional caption", examples=["Front cover"]),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.upload_artwork(db, archive_entry_id, artwork_type, file, caption=caption)
        audit_service.record(db, current_user, AuditAction.UPLOAD_ARTWORK, "ArchiveEntry", archive_entry_id, f"Uploaded {artwork_type.value} artwork")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch(
    "/replace",
    response_model=ArtworkReplaceResponse,
    summary="Replace artwork",
    description="Replace an existing artwork asset with a new upload.",
    response_description="Artwork replaced.",
)
def replace_artwork(
    archive_entry_id: str = Form(..., description="Archive entry ID", examples=["entry-uuid-1"]),
    artwork_type: ArtworkType = Form(..., description="Artwork type", examples=["banner"]),
    file: UploadFile = File(..., description="Artwork file"),
    screenshot_id: str | None = Form(None, description="Screenshot ID to replace", examples=["screenshot-uuid-1"]),
    caption: str | None = Form(None, description="Optional caption", examples=["Updated banner"]),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.replace_artwork(db, archive_entry_id, artwork_type, file, screenshot_id=screenshot_id, caption=caption)
        audit_service.record(db, current_user, AuditAction.REPLACE_ARTWORK, "ArchiveEntry", archive_entry_id, f"Replaced {artwork_type.value} artwork")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete(
    "/{artwork_id}",
    response_model=ArtworkDeleteResponse,
    summary="Delete artwork",
    description="Delete artwork by ID and optional type.",
    response_description="Artwork deleted.",
)
def delete_artwork(
    artwork_id: str,
    artwork_type: ArtworkType | None = Query(None, description="Artwork type", examples=["cover"]),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.delete_artwork(db, artwork_id, artwork_type=artwork_type)
        audit_service.record(
            db,
            current_user,
            AuditAction.DELETE_ARTWORK,
            "Artwork",
            artwork_id,
            f"Deleted {artwork_type.value if artwork_type else 'screenshot'} artwork",
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/missing",
    response_model=list[ArtworkMissingResponse],
    summary="List missing artwork",
    description="Return archive entries missing required artwork types.",
    response_description="Missing artwork entries retrieved.",
)
def list_missing_artwork(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    missing = service.list_missing_artwork(db)
    return [ArtworkMissingResponse(**entry) for entry in missing]


@router.post(
    "/auto-download",
    response_model=JobHistoryRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Auto download missing artwork",
    description="Queue a background job that downloads missing artwork for every entry; returns the job.",
)
def auto_download_missing_artwork(
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    jobs = JobService()
    # Downloading can take minutes, so it runs as a job; a running artwork job is reused instead of doubled.
    job = jobs.active_job(db, JobType.ARTWORK_REFRESH) or jobs.start_job(
        db, current_user, JobType.ARTWORK_REFRESH, details="Download missing artwork", task_kwargs={"mode": "fill"},
    )
    audit_service.record(db, current_user, AuditAction.AUTO_DOWNLOAD_ARTWORK, "Artwork", details=f"job {job.id}")
    return job