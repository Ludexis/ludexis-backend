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


@router.post(
    "/upload",
    response_model=ArtworkUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload artwork",
    description="Upload artwork for an archive entry. Accepts multipart form data.",
    response_description="Artwork uploaded.",
)
def upload_artwork(
    archive_entry_id: str = Form(..., description="Archive entry ID", example="entry-uuid-1"),
    artwork_type: ArtworkType = Form(..., description="Artwork type", example="cover"),
    file: UploadFile = File(..., description="Artwork file"),
    caption: str | None = Form(None, description="Optional caption", example="Front cover"),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.upload_artwork(db, archive_entry_id, artwork_type, file, caption=caption)
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
    archive_entry_id: str = Form(..., description="Archive entry ID", example="entry-uuid-1"),
    artwork_type: ArtworkType = Form(..., description="Artwork type", example="banner"),
    file: UploadFile = File(..., description="Artwork file"),
    screenshot_id: str | None = Form(None, description="Screenshot ID to replace", example="screenshot-uuid-1"),
    caption: str | None = Form(None, description="Optional caption", example="Updated banner"),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.replace_artwork(db, archive_entry_id, artwork_type, file, screenshot_id=screenshot_id, caption=caption)
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
    artwork_type: ArtworkType | None = Query(None, description="Artwork type", example="cover"),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        result = service.delete_artwork(db, artwork_id, artwork_type=artwork_type)
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
