from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.archive_entry import ArchiveEntryCreate, ArchiveEntryRead, ArchiveEntryUpdate, ArchiveMetadataUpdate
from app.services.archive_entry import ArchiveEntryService
from app.services.audit import AuditService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/archive-entries", tags=["archive_entries"])
service = ArchiveEntryService()
audit_service = AuditService()


@router.get(
    "/",
    response_model=list[ArchiveEntryRead],
    summary="List archive entries",
    description="Return archive entries with pagination.",
    response_description="Archive entries retrieved.",
)
def list_archive_entries(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list_entries(db, offset=offset, limit=limit)


@router.get(
    "/{archive_entry_id}",
    response_model=ArchiveEntryRead,
    summary="Get archive entry",
    description="Return a single archive entry by ID.",
    response_description="Archive entry retrieved.",
)
def read_archive_entry(
    archive_entry_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    return entry


@router.post(
    "/",
    response_model=ArchiveEntryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create archive entry",
    description="Create a new archive entry with optional related IDs.",
    response_description="Archive entry created.",
)
def create_archive_entry(
    data: ArchiveEntryCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    try:
        entry = service.create(db, data)
        audit_service.record(
            db,
            current_user,
            action="create",
            entity="ArchiveEntry",
            entity_id=entry.id,
            details=f"Created archive entry {entry.title}",
        )
        return entry
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch(
    "/{archive_entry_id}",
    response_model=ArchiveEntryRead,
    summary="Update archive entry",
    description="Update fields and relationships for an archive entry.",
    response_description="Archive entry updated.",
)
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
        updated = service.update(db, entry, data)
        audit_service.record(
            db,
            current_user,
            action="update",
            entity="ArchiveEntry",
            entity_id=updated.id,
            details=f"Updated archive entry {updated.title}",
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

@router.patch(
    "/{archive_entry_id}/metadata",
    response_model=ArchiveEntryRead,
    summary="Override archive metadata",
    description="Manually override archive metadata and prevent automatic metadata refresh.",
    response_description="Archive metadata overridden.",
)
def override_archive_metadata(
    archive_entry_id: str,
    data: ArchiveMetadataUpdate,
    current_user=Depends(
        require_permission(
            PermissionName.EDIT_METADATA
        )
    ),
    db: Session = Depends(get_db),
):
    entry = service.get(
        db,
        archive_entry_id,
    )

    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archive entry not found",
        )

    updated = service.update_metadata(
        db,
        entry,
        data,
    )

    audit_service.record(
        db,
        current_user,
        action="MANUAL_METADATA_OVERRIDE",
        entity="ArchiveEntry",
        entity_id=updated.id,
        details=f"Manual metadata override for {updated.title}",
    )

    return updated

@router.delete(
    "/{archive_entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete archive entry",
    description="Soft delete an archive entry by ID.",
    response_description="Archive entry deleted.",
)
def delete_archive_entry(
    archive_entry_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    service.delete(db, entry)
    audit_service.record(
        db,
        current_user,
        action="delete",
        entity="ArchiveEntry",
        entity_id=entry.id,
        details=f"Deleted archive entry {entry.title}",
    )
