from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.developer import DeveloperCreate, DeveloperRead, DeveloperUpdate
from app.services.developer import DeveloperService
from app.utils.enums import PermissionName
from app.schemas.developer import DeveloperCreate, DeveloperRead, DeveloperUpdate
from app.services.developer import DeveloperService

router = APIRouter(prefix="/developers", tags=["developers"])
service = DeveloperService()


@router.get("/", response_model=list[DeveloperRead])
def list_developers(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list(db, offset=offset, limit=limit)


@router.get("/{developer_id}", response_model=DeveloperRead)
def read_developer(
    developer_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    developer = service.get(db, developer_id)
    if developer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer not found")
    return developer


@router.post("/", response_model=DeveloperRead, status_code=status.HTTP_201_CREATED)
def create_developer(
    data: DeveloperCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    if service.repo.get_by_name(db, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Developer name already exists")
    return service.create(db, data)


@router.patch("/{developer_id}", response_model=DeveloperRead)
def update_developer(
    developer_id: str,
    data: DeveloperUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    developer = service.get(db, developer_id)
    if developer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer not found")
    return service.update(db, developer, data)


@router.delete("/{developer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_developer(
    developer_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    developer = service.get(db, developer_id)
    if developer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Developer not found")
    service.delete(db, developer)
