from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import ensure_permission, get_current_active_user, get_optional_current_user, require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.auth import PasswordResetRequest
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.audit_log import AuditLogService
from app.utils.audit_actions import AuditAction
from app.utils.enums import PermissionName

router = APIRouter(prefix="/users", tags=["users"])
user_repo = UserRepository()
role_repo = RoleRepository()
audit_log_service = AuditLogService()


def _load_roles(db: Session, role_ids: list[str]) -> list:
    roles = []
    for role_id in role_ids:
        role = role_repo.get(db, role_id)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role not found: {role_id}",
            )
        roles.append(role)
    return roles


def _require_manage_users_if_initialized(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
) -> User | None:
    if not user_repo.has_any(db):
        return None
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    ensure_permission(current_user, PermissionName.MANAGE_USERS)
    return current_user


@router.get(
    "/",
    response_model=list[UserRead],
    summary="List users",
    description="Return users with pagination.",
    response_description="Users retrieved.",
)
def list_users(
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    return user_repo.list_items(db, offset=skip, limit=limit)


@router.post(
    "/",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description="Create a new user and optionally assign roles.",
    response_description="User created.",
)
def create_user(
    data: UserCreate,
    current_user: User | None = Depends(_require_manage_users_if_initialized),
    db: Session = Depends(get_db),
):
    initialized = user_repo.has_any(db)
    if user_repo.get_by_username(db, data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already in use",
        )
    if user_repo.get_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already in use",
        )

    hashed_password = hash_password(data.password)
    user = user_repo.create(db, {
        "username": data.username,
        "email": data.email,
        "hashed_password": hashed_password,
        "is_active": True if not initialized else data.is_active,
        "is_superuser": True if not initialized else data.is_superuser,
    })

    if initialized and data.role_ids:
        user.roles = _load_roles(db, data.role_ids)
        db.add(user)
        db.commit()
        db.refresh(user)

    audit_log_service.log(
        db,
        action=AuditAction.CREATE_USER,
        entity="User",
        entity_id=user.id,
        user_id=current_user.id if current_user else None,
        details=f"Created user '{user.username}'",
    )

    if initialized and data.role_ids:
        for role in user.roles:
            audit_log_service.log(
                db,
                action=AuditAction.ASSIGN_ROLE,
                entity="User",
                entity_id=user.id,
                user_id=current_user.id if current_user else None,
                details=f"Assigned role '{role.name}' to user '{user.username}'",
            )

    return user


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = user_repo.get_active(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user",
    description="Return a user by ID.",
    response_description="User retrieved.",
)
def read_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    return _get_user_or_404(db, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user",
    description="Update a user record and roles.",
    response_description="User updated.",
)
def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    old_roles = list(user.roles)
    old_role_ids = {role.id for role in old_roles}
    assigned_roles: list = []
    removed_roles: list = []

    if data.username is not None:
        if user.username != data.username and user_repo.get_by_username(db, data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already in use",
            )
        user.username = data.username

    if data.email is not None:
        if user.email != data.email and user_repo.get_by_email(db, data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use",
            )
        user.email = data.email

    if data.password is not None:
        user.hashed_password = hash_password(data.password)

    if data.is_active is not None:
        user.is_active = data.is_active

    if data.is_superuser is not None:
        user.is_superuser = data.is_superuser

    if data.role_ids is not None:
        new_roles = _load_roles(db, data.role_ids)
        new_role_ids = {role.id for role in new_roles}
        assigned_roles = [role for role in new_roles if role.id not in old_role_ids]
        removed_roles = [role for role in old_roles if role.id not in new_role_ids]
        user.roles = new_roles

    db.add(user)
    db.commit()
    db.refresh(user)
    audit_log_service.log(
        db,
        action=AuditAction.UPDATE_USER,
        entity="User",
        entity_id=user.id,
        user_id=current_user.id,
        details=f"Updated user '{user.username}'",
    )
    for role in assigned_roles:
        audit_log_service.log(
            db,
            action=AuditAction.ASSIGN_ROLE,
            entity="User",
            entity_id=user.id,
            user_id=current_user.id,
            details=f"Assigned role '{role.name}' to user '{user.username}'",
        )
    for role in removed_roles:
        audit_log_service.log(
            db,
            action=AuditAction.REMOVE_ROLE,
            entity="User",
            entity_id=user.id,
            user_id=current_user.id,
            details=f"Removed role '{role.name}' from user '{user.username}'",
        )
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Soft delete a user by ID.",
    response_description="User deleted.",
)
def delete_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    user = _get_user_or_404(db, user_id)
    user_repo.delete(db, user)
    audit_log_service.log(
        db,
        action=AuditAction.DELETE_USER,
        entity="User",
        entity_id=user.id,
        user_id=current_user.id,
        details=f"Deleted user '{user.username}'",
    )


@router.post(
    "/{user_id}/activate",
    response_model=UserRead,
    summary="Activate user",
    description="Activate a user account.",
    response_description="User activated.",
)
def activate_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate your own account",
        )
    user = _get_user_or_404(db, user_id)
    return user_repo.activate(db, user)


@router.post(
    "/{user_id}/deactivate",
    response_model=UserRead,
    summary="Deactivate user",
    description="Deactivate a user account.",
    response_description="User deactivated.",
)
def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )
    user = _get_user_or_404(db, user_id)
    return user_repo.deactivate(db, user)


@router.post(
    "/{user_id}/reset-password",
    response_model=UserRead,
    summary="Reset user password",
    description="Reset a user's password.",
    response_description="Password reset.",
)
def reset_password(
    user_id: str,
    data: PasswordResetRequest,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    user.hashed_password = hash_password(data.password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
