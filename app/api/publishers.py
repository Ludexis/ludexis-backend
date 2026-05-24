from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.publisher import PublisherCreate, PublisherRead, PublisherUpdate
from app.services.publisher import PublisherService
from app.utils.enums import PermissionName
from app.schemas.publisher import PublisherCreate, PublisherRead, PublisherUpdate
from app.services.publisher import PublisherService

router = APIRouter(prefix="/publishers", tags=["publishers"])
service = PublisherService()


@router.get("/", response_model=list[PublisherRead])
def list_publishers(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list(db, offset=offset, limit=limit)


@router.get("/{publisher_id}", response_model=PublisherRead)
def read_publisher(
    publisher_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    publisher = service.get(db, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher not found")
    return publisher


@router.post("/", response_model=PublisherRead, status_code=status.HTTP_201_CREATED)
def create_publisher(
    data: PublisherCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    if service.repo.get_by_name(db, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Publisher name already exists")
    return service.create(db, data)


@router.patch("/{publisher_id}", response_model=PublisherRead)
def update_publisher(
    publisher_id: str,
    data: PublisherUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    publisher = service.get(db, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher not found")
    return service.update(db, publisher, data)


@router.delete("/{publisher_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_publisher(
    publisher_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    publisher = service.get(db, publisher_id)
    if publisher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Publisher not found")
    service.delete(db, publisher)
