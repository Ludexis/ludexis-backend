from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.franchise import FranchiseCreate, FranchiseRead, FranchiseUpdate
from app.services.audit import AuditService
from app.services.franchise import FranchiseService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/franchises", tags=["franchises"])
service = FranchiseService()
audit_service = AuditService()


@router.get(
    "/",
    response_model=list[FranchiseRead],
    summary="List franchises",
    description="Return franchises with pagination.",
    response_description="Franchises retrieved.",
)
def list_franchises(
    response: Response,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
    q: str | None = None,
):
    items = service.list_items(db, offset=offset, limit=limit, q=q)
    response.headers["X-Total-Count"] = str(service.count(db, q=q))
    return items


@router.get(
    "/{franchise_id}",
    response_model=FranchiseRead,
    summary="Get franchise",
    description="Return a single franchise by ID.",
    response_description="Franchise retrieved.",
)
def read_franchise(
    franchise_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    franchise = service.get(db, franchise_id)
    if franchise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")
    return franchise


@router.post(
    "/",
    response_model=FranchiseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create franchise",
    description="Create a new franchise record.",
    response_description="Franchise created.",
)
def create_franchise(
    data: FranchiseCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    if service.repo.get_by_name(db, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Franchise name already exists")
    franchise = service.create(db, data)
    audit_service.record(
        db,
        current_user,
        action="create",
        entity="Franchise",
        entity_id=franchise.id,
        details=f"Created franchise {franchise.name}",
    )
    return franchise


@router.patch(
    "/{franchise_id}",
    response_model=FranchiseRead,
    summary="Update franchise",
    description="Update a franchise record.",
    response_description="Franchise updated.",
)
def update_franchise(
    franchise_id: str,
    data: FranchiseUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = service.get(db, franchise_id)
    if franchise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")
    updated = service.update(db, franchise, data)
    audit_service.record(
        db,
        current_user,
        action="update",
        entity="Franchise",
        entity_id=updated.id,
        details=f"Updated franchise {updated.name}",
    )
    return updated


@router.delete(
    "/{franchise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete franchise",
    description="Soft delete a franchise by ID.",
    response_description="Franchise deleted.",
)
def delete_franchise(
    franchise_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = service.get(db, franchise_id)
    if franchise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")
    service.delete(db, franchise)
    audit_service.record(
        db,
        current_user,
        action="delete",
        entity="Franchise",
        entity_id=franchise.id,
        details=f"Deleted franchise {franchise.name}",
    )
