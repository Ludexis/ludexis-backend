from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRead

from app.models.permission import Permission
from app.models.role import Role
from app.utils.enums import PermissionName, RoleName

router = APIRouter(prefix="/setup", tags=["setup"])
user_repo = UserRepository()

def seed_permissions(db: Session) -> dict[str, Permission]:
    permissions = {}

    for permission_name in PermissionName:
        permission = (
            db.query(Permission)
            .filter(Permission.name == permission_name.value)
            .first()
        )

        if permission is None:
            permission = Permission(
                name=permission_name.value,
                description=permission_name.value.replace("_", " ").title(),
            )
            db.add(permission)

        permissions[permission_name.value] = permission

    db.flush()
    return permissions


def seed_roles(db: Session, permissions: dict[str, Permission]) -> dict[str, Role]:
    role_definitions = {
        RoleName.ADMINISTRATOR.value: list(PermissionName),
        RoleName.MODERATOR.value: [
            PermissionName.VIEW_LIBRARY,
            PermissionName.EDIT_METADATA,
            PermissionName.MANAGE_COLLECTIONS,
            PermissionName.RUN_SCANS,
        ],
        RoleName.USER.value: [
            PermissionName.VIEW_LIBRARY,
        ],
        RoleName.READ_ONLY.value: [
            PermissionName.VIEW_LIBRARY,
        ],
    }

    roles = {}

    for role_name, role_permissions in role_definitions.items():
        role = db.query(Role).filter(Role.name == role_name).first()

        if role is None:
            role = Role(
                name=role_name,
                description=f"{role_name} role",
            )
            db.add(role)

        role.permissions = [
            permissions[p.value]
            for p in role_permissions
        ]

        roles[role_name] = role

    db.flush()
    return roles

@router.get("/status")
def setup_status(db: Session = Depends(get_db)):
    initialized = user_repo.has_any(db)
    return {"initialized": initialized}


@router.post("/initialize", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def initialize_system(data: UserCreate, db: Session = Depends(get_db)):
    if user_repo.has_any(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System already initialized")

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

    permissions = seed_permissions(db)
    roles = seed_roles(db, permissions)

    hashed_password = hash_password(data.password)

    user = user_repo.create(
        db,
        {
            "username": data.username,
            "email": data.email,
            "hashed_password": hashed_password,
            "is_active": True,
            "is_superuser": True,
        },
    )

    user.roles.append(
        roles[RoleName.ADMINISTRATOR.value]
    )

    db.commit()
    db.refresh(user)

    return user
