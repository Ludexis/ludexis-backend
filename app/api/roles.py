from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.session import get_db
from app.repositories.permission import PermissionRepository
from app.repositories.role import RoleRepository
from app.schemas.permission import PermissionRead
from app.schemas.role import RoleCreate, RoleRead, RoleUpdate
from app.services.audit_log import AuditLogService
from app.utils.audit_actions import AuditAction
from app.utils.enums import PermissionName

router = APIRouter(prefix="/roles", tags=["roles"])
role_repo = RoleRepository()
permission_repo = PermissionRepository()
audit_log_service = AuditLogService()


def _load_permissions(db: Session, permission_ids: list[str]) -> list:
    permissions = []
    for permission_id in permission_ids:
        permission = permission_repo.get(db, permission_id)
        if permission is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Permission not found: {permission_id}",
            )
        permissions.append(permission)
    return permissions


@router.get(
    "/",
    response_model=list[RoleRead],
    summary="List roles",
    description="Return all roles.",
    response_description="Roles retrieved.",
)
def list_roles(
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    return role_repo.list_items(db)


@router.post(
    "/",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create role",
    description="Create a new role and assign permissions.",
    response_description="Role created.",
)
def create_role(
    data: RoleCreate,
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    role = role_repo.create(db, {"name": data.name, "description": data.description})
    if data.permission_ids:
        role.permissions = _load_permissions(db, data.permission_ids)
        db.add(role)
        db.commit()
        db.refresh(role)
    audit_log_service.log(
        db,
        action=AuditAction.CREATE_ROLE,
        entity="Role",
        entity_id=role.id,
        user_id=current_user.id,
        details=f"Created role '{role.name}'",
    )
    return role


@router.get(
    "/{role_id}",
    response_model=RoleRead,
    summary="Get role",
    description="Return a role by ID.",
    response_description="Role retrieved.",
)
def read_role(
    role_id: str,
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    role = role_repo.get(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


@router.patch(
    "/{role_id}",
    response_model=RoleRead,
    summary="Update role",
    description="Update role attributes and permissions.",
    response_description="Role updated.",
)
def update_role(
    role_id: str,
    data: RoleUpdate,
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    role = role_repo.get(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    if data.name is not None:
        role.name = data.name

    if data.description is not None:
        role.description = data.description

    if data.permission_ids is not None:
        role.permissions = _load_permissions(db, data.permission_ids)

    db.add(role)
    db.commit()
    db.refresh(role)
    audit_log_service.log(
        db,
        action=AuditAction.UPDATE_ROLE,
        entity="Role",
        entity_id=role.id,
        user_id=current_user.id,
        details=f"Updated role '{role.name}'",
    )
    return role


@router.delete(
    "/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete role",
    description="Delete a role by ID.",
    response_description="Role deleted.",
)
def delete_role(
    role_id: str,
    current_user=Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    role = role_repo.get(db, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    role_repo.delete(db, role)
    audit_log_service.log(
        db,
        action=AuditAction.DELETE_ROLE,
        entity="Role",
        entity_id=role.id,
        user_id=current_user.id,
        details=f"Deleted role '{role.name}'",
    )
