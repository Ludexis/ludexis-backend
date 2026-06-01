from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.library import LibraryCreate, LibraryRead, LibraryUpdate
from app.services.audit import AuditService
from app.services.library import LibraryService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/libraries", tags=["libraries"])
service = LibraryService()
audit_service = AuditService()


@router.get("/", response_model=list[LibraryRead])
def list_libraries(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list_items(db, offset=offset, limit=limit)


@router.get("/{library_id}", response_model=LibraryRead)
def read_library(
    library_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    library = service.get(db, library_id)
    if library is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    return library


@router.post("/", response_model=LibraryRead, status_code=status.HTTP_201_CREATED)
def create_library(
    data: LibraryCreate,
    current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)),
    db: Session = Depends(get_db),
):
    try:
        library = service.create(db, data)
        audit_service.record(
            db,
            current_user,
            action="create",
            entity="Library",
            entity_id=library.id,
            details=f"Created library {library.name}",
        )
        return library
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{library_id}", response_model=LibraryRead)
def update_library(
    library_id: str,
    data: LibraryUpdate,
    current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)),
    db: Session = Depends(get_db),
):
    library = service.get(db, library_id)
    if library is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    try:
        updated = service.update(db, library, data)
        audit_service.record(
            db,
            current_user,
            action="update",
            entity="Library",
            entity_id=updated.id,
            details=f"Updated library {updated.name}",
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{library_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_library(
    library_id: str,
    current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)),
    db: Session = Depends(get_db),
):
    library = service.get(db, library_id)
    if library is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Library not found")
    service.delete(db, library)
    audit_service.record(
        db,
        current_user,
        action="delete",
        entity="Library",
        entity_id=library.id,
        details=f"Deleted library {library.name}",
    )