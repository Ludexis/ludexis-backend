
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.repositories.user import UserRepository
from app.utils.enums import PermissionName, RoleName

logger = get_logger(__name__)
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


def ensure_default_admin(db: Session) -> User | None:
    """On a server with no accounts, seed roles and create the default administrator.

    The account must choose a new password at its first sign-in; until then the API serves it nothing else.
    """
    if user_repo.has_any(db):
        return None
    roles = seed_roles(db, seed_permissions(db))
    admin = User(
        username=settings.DEFAULT_ADMIN_USERNAME,
        email=settings.DEFAULT_ADMIN_EMAIL,
        hashed_password=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
        is_active=True,
        is_superuser=True,
        allow_restricted=True,
        must_change_password=True,
    )
    admin.roles.append(roles[RoleName.ADMINISTRATOR.value])
    db.add(admin)
    try:
        db.commit()
    except IntegrityError:
        # Another process created it first.
        db.rollback()
        return None
    logger.warning(
        "Created the default administrator '%s'; sign in with the default password and choose a new one",
        admin.username,
    )
    return admin
