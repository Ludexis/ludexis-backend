from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.repositories.role import RoleRepository
from app.repositories.user import UserRepository
from app.schemas.auth import PasswordResetRequest
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.utils.enums import PermissionName

router = APIRouter(prefix="/users", tags=["users"])
user_repo = UserRepository()
role_repo = RoleRepository()


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


@router.get("/", response_model=list[UserRead])
def list_users(
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    return user_repo.list(db, offset=skip, limit=limit)


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
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
        "is_active": data.is_active,
        "is_superuser": data.is_superuser,
    })

    if data.role_ids:
        user.roles = _load_roles(db, data.role_ids)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = user_repo.get_active(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.get("/{user_id}", response_model=UserRead)
def read_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    return _get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)

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
        user.roles = _load_roles(db, data.role_ids)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    user_repo.delete(db, user)


@router.post("/{user_id}/activate", response_model=UserRead)
def activate_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    return user_repo.activate(db, user)


@router.post("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user(
    user_id: str,
    current_user: User = Depends(require_permission(PermissionName.MANAGE_USERS)),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, user_id)
    return user_repo.deactivate(db, user)


@router.post("/{user_id}/reset-password", response_model=UserRead)
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
