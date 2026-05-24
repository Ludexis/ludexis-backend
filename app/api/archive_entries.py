from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.archive_entry import ArchiveEntryCreate, ArchiveEntryRead, ArchiveEntryUpdate
from app.services.archive_entry import ArchiveEntryService
from app.utils.enums import PermissionName
from app.schemas.archive_entry import ArchiveEntryCreate, ArchiveEntryRead, ArchiveEntryUpdate
from app.services.archive_entry import ArchiveEntryService

router = APIRouter(prefix="/archive-entries", tags=["archive_entries"])
service = ArchiveEntryService()


@router.get("/", response_model=list[ArchiveEntryRead])
def list_archive_entries(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list(db, offset=offset, limit=limit)


@router.get("/{archive_entry_id}", response_model=ArchiveEntryRead)
def read_archive_entry(
    archive_entry_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    return entry


@router.post("/", response_model=ArchiveEntryRead, status_code=status.HTTP_201_CREATED)
def create_archive_entry(
    data: ArchiveEntryCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        return service.create(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{archive_entry_id}", response_model=ArchiveEntryRead)
def update_archive_entry(
    archive_entry_id: str,
    data: ArchiveEntryUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    try:
        return service.update(db, entry, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{archive_entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_archive_entry(
    archive_entry_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    service.delete(db, entry)
