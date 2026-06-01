from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.publisher import PublisherCreate, PublisherRead, PublisherUpdate
from app.services.audit import AuditService
from app.services.publisher import PublisherService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/publishers", tags=["publishers"])
service = PublisherService()
audit_service = AuditService()


@router.get(
    "/",
    response_model=list[PublisherRead],
    summary="List publishers",
    description="Return publishers with pagination.",
    response_description="Publishers retrieved.",
)
def list_publishers(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list_items(db, offset=offset, limit=limit)


@router.get(
    "/{publisher_id}",
    response_model=PublisherRead,
    summary="Get publisher",
    description="Return a single publisher by ID.",
    response_description="Publisher retrieved.",
)
def read_publisher(
    publisher_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    publisher = service.get(db, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher not found")
    return publisher


@router.post(
    "/",
    response_model=PublisherRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create publisher",
    description="Create a new publisher record.",
    response_description="Publisher created.",
)
def create_publisher(
    data: PublisherCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    if service.repo.get_by_name(db, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Publisher name already exists")
    publisher = service.create(db, data)
    audit_service.record(
        db,
        current_user,
        action="create",
        entity="Publisher",
        entity_id=publisher.id,
        details=f"Created publisher {publisher.name}",
    )
    return publisher


@router.patch(
    "/{publisher_id}",
    response_model=PublisherRead,
    summary="Update publisher",
    description="Update a publisher record.",
    response_description="Publisher updated.",
)
def update_publisher(
    publisher_id: str,
    data: PublisherUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    publisher = service.get(db, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher not found")
    updated = service.update(db, publisher, data)
    audit_service.record(
        db,
        current_user,
        action="update",
        entity="Publisher",
        entity_id=updated.id,
        details=f"Updated publisher {updated.name}",
    )
    return updated


@router.delete(
    "/{publisher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete publisher",
    description="Soft delete a publisher by ID.",
    response_description="Publisher deleted.",
)
def delete_publisher(
    publisher_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    publisher = service.get(db, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher not found")
    service.delete(db, publisher)
    audit_service.record(
        db,
        current_user,
        action="delete",
        entity="Publisher",
        entity_id=publisher.id,
        details=f"Deleted publisher {publisher.name}",
    )
