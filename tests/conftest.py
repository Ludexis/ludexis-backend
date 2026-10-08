import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Tests save artwork; keep it out of the artwork folder a local .env points at.
os.environ["ARTWORK_STORAGE_PATH"] = tempfile.mkdtemp(prefix="ludexis-test-artwork-")

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

@pytest.fixture(autouse=True)
def no_celery_broker(monkeypatch):
    # Tasks open their own sessions on the application database, so tests must never queue real
    # messages: a running worker would execute them against the live database.
    from itertools import count
    from types import SimpleNamespace
    from celery.app.task import Task

    task_ids = count(1)
    monkeypatch.setattr(
        Task,
        "apply_async",
        lambda self, *args, **kwargs: SimpleNamespace(id=f"test-task-{next(task_ids)}"),
    )


class _MemoryRedis:
    """Enough of Redis for the login rate limiter, fresh for every test."""

    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key, seconds):
        return True

    def ttl(self, key):
        return 900

    def delete(self, key):
        self.values.pop(key, None)


@pytest.fixture(autouse=True)
def isolated_login_limiter(monkeypatch):
    from app.api import auth

    monkeypatch.setattr(auth.login_limiter, "_client", _MemoryRedis())


@pytest.fixture(autouse=True)
def stateless_test_clients(monkeypatch):
    # Login sets session cookies; tests authenticate explicitly, so clients must not carry them to later requests.
    import httpx

    monkeypatch.setattr(httpx.Client, "cookies", property(lambda self: httpx.Cookies(), lambda self, value: None))
