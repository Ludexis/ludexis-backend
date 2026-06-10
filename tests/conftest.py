import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from main import app
from app.db.session import get_db

from app.db.base import Base
from app.core.security import hash_password
from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.utils.enums import RoleName, PermissionName

from tests.test_db import (
    test_engine,
    TestingSessionLocal,
)

@pytest.fixture(scope="session", autouse=True)
def setup_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()

    permissions = {}

    for permission_name in PermissionName:
        permission = Permission(
            name=permission_name.value,
            description=permission_name.value,
        )
        db.add(permission)
        permissions[permission_name.value] = permission

    admin_role = Role(
        name=RoleName.ADMINISTRATOR.value,
        description="Administrator role",
    )

    admin_role.permissions = list(
        permissions.values()
    )

    db.add(admin_role)

    admin_user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=hash_password(
            "Admin123!"
        ),
        is_active=True,
        is_superuser=True,
    )

    admin_user.roles.append(admin_role)

    db.add(admin_user)

    user_role = Role(
        name="User",
        description="Regular user role",
    )

    db.add(user_role)

    test_user = User(
        username="testuser",
        email="testuser@example.com",
        hashed_password=hash_password(
            "Test123!"
        ),
        is_active=True,
        is_superuser=False,
    )

    test_user.roles.append(user_role)

    db.add(test_user)

    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db