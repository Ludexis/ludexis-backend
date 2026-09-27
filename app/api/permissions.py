from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.session import get_db
from app.repositories.permission import PermissionRepository
from app.schemas.permission import PermissionCreate, PermissionRead
from app.services.audit import AuditService
from app.utils.audit_actions import AuditAction
from app.utils.enums import PermissionName

router = APIRouter(prefix="/permissions", tags=["permissions"])
permission_repo = PermissionRepository()
audit_service = AuditService()


@router.get(
    "/",
    response_model=list[PermissionRead],
    summary="List permissions",
    description="Return all permissions.",
    response_description="Permissions retrieved.",
)
def list_permissions(
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    return permission_repo.list_items(db)


@router.post(
    "/",
    response_model=PermissionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create permission",
    description="Create a new permission.",
    response_description="Permission created.",
)
def create_permission(
    data: PermissionCreate,
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    if permission_repo.get_by_name(db, data.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission already exists",
        )
    permission = permission_repo.create(db, {"name": data.name, "description": data.description})
    audit_service.record(db, current_user, AuditAction.CREATE_PERMISSION, "Permission", permission.id, f"Created permission {permission.name}")
    return permission


@router.get(
    "/{permission_id}",
    response_model=PermissionRead,
    summary="Get permission",
    description="Return a permission by ID.",
    response_description="Permission retrieved.",
)
def read_permission(
    permission_id: str,
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    permission = permission_repo.get(db, permission_id)
    if permission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    return permission
