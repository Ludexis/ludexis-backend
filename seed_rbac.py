from app.db.session import SessionLocal
from app.models.permission import Permission
from app.models.role import Role
from app.utils.enums import PermissionName, RoleName

db = SessionLocal()
print("DB connected")

try:
    print("Creating permissions...")
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
    print("Permissions done")

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

    for role_name, role_permissions in role_definitions.items():
        print("Creating roles...")

        role = (
            db.query(Role)
            .filter(Role.name == role_name)
            .first()
        )

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
    print("Roles done")
    print("Committing...")
    db.commit()
    print("Finished")

    print("RBAC seeded successfully")

finally:
    db.close()