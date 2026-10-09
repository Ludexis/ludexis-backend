from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.archive_entry import (
    ArchiveEntryCreate, ArchiveEntryFlags, ArchiveEntryFlagsUpdate, ArchiveEntryRead, ArchiveEntryUpdate, ArchiveIdentifyRequest, ArchiveIdentifyResult, ArchiveLocationResult, ArchiveMetadataUpdate,
)
from app.schemas.screenshot import ScreenshotRead
from app.core.access import RESTRICTED_PROVIDERS, acting_as, annotate_flags, restricted_sources_allowed, set_flags
from app.services.archive_entry import ArchiveEntryService
from app.services.audit import AuditService
from app.utils.enums import PermissionName
from app.services.scanner import ScannerService
from app.schemas.duplicates import DuplicateGroup
from app.repositories.screenshot import ScreenshotRepository
from app.services.grouping import version_order
from app.services.job import JobService
from app.services.metadata import MetadataService
from app.utils.audit_actions import AuditAction
from app.utils.enums import JobType
from app.utils import file_manager
from pathlib import Path


router = APIRouter(prefix="/archive-entries", tags=["archive_entries"])
service = ArchiveEntryService()
audit_service = AuditService()
scanner_service = ScannerService()
screenshot_repo = ScreenshotRepository()


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
    return annotate_flags(db, current_user, service.list_entries(db, offset=offset, limit=limit, viewer=current_user))

@router.get(
    "/duplicates",
    response_model=list[DuplicateGroup],
    summary="Find duplicate archives",
    description="Return archive entries sharing identical file hashes.",
)
def list_duplicates(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return scanner_service.find_duplicates(db, viewer=current_user)

@router.get(
    "/{archive_entry_id}/screenshots",
    response_model=list[ScreenshotRead],
    summary="List screenshots",
    description="Return screenshots for an archive entry.",
)
def list_screenshots(
    archive_entry_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id, current_user)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    return screenshot_repo.list_by_entry(db, archive_entry_id)


@router.get(
    "/{archive_entry_id}/versions",
    response_model=list[ArchiveEntryRead],
    summary="List versions",
    description="Return every version of the entry's game, newest first.",
)
def list_versions(
    archive_entry_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id, current_user)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    versions = annotate_flags(db, current_user, service.repo.list_versions(db, entry, viewer=current_user))
    return sorted(versions, key=lambda e: version_order(e.version), reverse=True)


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
    entry = service.get(db, archive_entry_id, current_user)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    return annotate_flags(db, current_user, [entry])[0]


@router.put(
    "/{archive_entry_id}/flags",
    response_model=ArchiveEntryFlags,
    summary="Mark favourite or completed",
    description="Set the current user's favourite and completed marks on a game; omitted fields keep their value.",
)
def set_archive_flags(
    archive_entry_id: str,
    data: ArchiveEntryFlagsUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id, current_user)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    # Versions of a game share one library card, so they share the marks too.
    versions = [entry] + [version for version in service.repo.list_versions(db, entry, viewer=current_user) if version.id != entry.id]
    flag = set_flags(db, current_user, versions, data.is_favorite, data.is_completed)
    return {"is_favorite": flag.favorite, "is_completed": flag.completed}


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
    entry = service.get(db, archive_entry_id, current_user)
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
    entry = service.get(db, archive_entry_id, current_user)

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

@router.post(
    "/{archive_entry_id}/identify",
    response_model=ArchiveIdentifyResult,
    summary="Identify archive entry",
    description="Match the entry, and every unlocked version of the same game, to a chosen provider record. "
    "Metadata is applied at once; fresh artwork is downloaded by the returned job.",
    response_description="Archive entry identified.",
)
def identify_archive_entry(
    archive_entry_id: str,
    data: ArchiveIdentifyRequest,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id, current_user)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    with acting_as(current_user.id):
        if data.provider in RESTRICTED_PROVIDERS and not restricted_sources_allowed(db):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Provider not available to this account")
        updated = MetadataService().identify(db, entry, data.provider, data.provider_id)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider record not found")
    job = JobService().start_job(
        db, current_user, JobType.ARTWORK_REFRESH, details=f"Replace artwork for {entry.title}",
        task_kwargs={"mode": "replace", "entry_ids": [item.id for item in updated]},
    )
    audit_service.record(
        db, current_user, AuditAction.IDENTIFY_ARCHIVE, "ArchiveEntry", entity_id=entry.id,
        details=f"Identified {entry.title} as {data.provider} {data.provider_id}",
    )
    db.refresh(entry)
    return {"entry": entry, "updated_entries": len(updated), "artwork_job": job}


@router.post(
    "/{archive_entry_id}/open-location",
    response_model=ArchiveLocationResult,
    summary="Open archive location",
    description="Show the entry's file or folder in the file manager of the machine running the server. "
    "404 when the file, folder or drive is not there.",
    response_description="Where the entry is, and whether a file manager was opened.",
)
def open_archive_location(
    archive_entry_id: str,
    current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)),
    db: Session = Depends(get_db),
):
    entry = service.get(db, archive_entry_id, current_user)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archive entry not found")
    path = Path(entry.file_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Directory not found")
    return {"path": str(path), "opened": file_manager.reveal(path)}


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
    entry = service.get(db, archive_entry_id, current_user)
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

