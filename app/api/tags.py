from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.tag import TagCreate, TagRead, TagUpdate
from app.services.tag import TagService
from app.utils.enums import PermissionName
from app.schemas.tag import TagCreate, TagRead, TagUpdate
from app.services.tag import TagService

router = APIRouter(prefix="/tags", tags=["tags"])
service = TagService()


@router.get("/", response_model=list[TagRead])
def list_tags(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list(db, offset=offset, limit=limit)


@router.get("/{tag_id}", response_model=TagRead)
def read_tag(
    tag_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    tag = service.get(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return tag


@router.post("/", response_model=TagRead, status_code=status.HTTP_201_CREATED)
def create_tag(
    data: TagCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    if service.repo.get_by_name(db, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tag name already exists")
    return service.create(db, data)


@router.patch("/{tag_id}", response_model=TagRead)
def update_tag(
    tag_id: str,
    data: TagUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    tag = service.get(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    return service.update(db, tag, data)


@router.delete("/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    tag = service.get(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    service.delete(db, tag)
