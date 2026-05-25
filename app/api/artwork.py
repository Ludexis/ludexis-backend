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
from app.utils.artwork import ArtworkType

router = APIRouter(prefix="/artwork", tags=["artwork"])
service = ArtworkService()


@router.post("/upload", response_model=ArtworkUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_artwork(
    archive_entry_id: str = Form(...),
    artwork_type: ArtworkType = Form(...),
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.upload_artwork(db, archive_entry_id, artwork_type, file, caption=caption)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/replace", response_model=ArtworkReplaceResponse)
def replace_artwork(
    archive_entry_id: str = Form(...),
    artwork_type: ArtworkType = Form(...),
    file: UploadFile = File(...),
    screenshot_id: str | None = Form(None),
    caption: str | None = Form(None),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.replace_artwork(db, archive_entry_id, artwork_type, file, screenshot_id=screenshot_id, caption=caption)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{artwork_id}", response_model=ArtworkDeleteResponse)
def delete_artwork(
    artwork_id: str,
    artwork_type: ArtworkType | None = Query(None),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.delete_artwork(db, artwork_id, artwork_type=artwork_type)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/missing", response_model=list[ArtworkMissingResponse])
def list_missing_artwork(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    missing = service.list_missing_artwork(db)
    return [ArtworkMissingResponse(**entry) for entry in missing]
