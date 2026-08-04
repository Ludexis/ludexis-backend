from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.tag import TagCreate, TagRead, TagUpdate
from app.services.audit import AuditService
from app.services.tag import TagService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/tags", tags=["tags"])
service = TagService()
audit_service = AuditService()


@router.get(
    "/",
    response_model=list[TagRead],
    summary="List tags",
    description="Return tags with pagination.",
    response_description="Tags retrieved.",
)
def list_tags(
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
    "/{tag_id}",
    response_model=TagRead,
    summary="Get tag",
    description="Return a single tag by ID.",
    response_description="Tag retrieved.",
)
def read_tag(
    tag_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    tag = service.get(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return tag


@router.post(
    "/",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create tag",
    description="Create a new tag.",
    response_description="Tag created.",
)
def create_tag(
    data: TagCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    if service.repo.get_by_name(db, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name already exists")
    tag = service.create(db, data)
    audit_service.record(
        db,
        current_user,
        action="create",
        entity="Tag",
        entity_id=tag.id,
        details=f"Created tag {tag.name}",
    )
    return tag


@router.patch(
    "/{tag_id}",
    response_model=TagRead,
    summary="Update tag",
    description="Update a tag record.",
    response_description="Tag updated.",
)
def update_tag(
    tag_id: str,
    data: TagUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    tag = service.get(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    updated = service.update(db, tag, data)
    audit_service.record(
        db,
        current_user,
        action="update",
        entity="Tag",
        entity_id=updated.id,
        details=f"Updated tag {updated.name}",
    )
    return updated


@router.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Soft delete a tag by ID.",
    response_description="Tag deleted.",
)
def delete_tag(
    tag_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    tag = service.get(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    service.delete(db, tag)
    audit_service.record(
        db,
        current_user,
        action="delete",
        entity="Tag",
        entity_id=tag.id,
        details=f"Deleted tag {tag.name}",
    )
