import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.services import bootstrap
from main import app
from tests.test_db import TestingSessionLocal

client = TestClient(app)


def test_fresh_server_gets_an_administrator_that_must_change_password():
    name = f"admin-{uuid.uuid4().hex[:8]}"
    db = TestingSessionLocal()
    try:
        with patch.object(bootstrap.user_repo, "has_any", return_value=False), \
                patch.object(settings, "DEFAULT_ADMIN_USERNAME", name), \
                patch.object(settings, "DEFAULT_ADMIN_EMAIL", f"{name}@example.com"):
            admin = bootstrap.ensure_default_admin(db)
        assert admin.must_change_password and admin.is_superuser
        assert [role.name for role in admin.roles] == ["Administrator"]
        # Accounts already exist: nothing is created.
        assert bootstrap.ensure_default_admin(db) is None
    finally:
        db.query(User).filter_by(username=name).delete()
        db.commit()
        db.close()


def test_default_password_must_be_changed_before_anything_else():
    name = f"admin-{uuid.uuid4().hex[:8]}"
    db = TestingSessionLocal()
    db.add(User(username=name, email=f"{name}@example.com", hashed_password=hash_password("admin"),
                is_superuser=True, must_change_password=True))
    db.commit()
    db.close()

    with patch.object(settings, "DEFAULT_ADMIN_USERNAME", name):
        assert client.get("/api/setup/status").json() == {"initialized": True, "default_login": name}

        tokens = client.post("/api/auth/login", json={"username": name, "password": "admin"}).json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        assert client.get("/api/auth/me", headers=headers).json()["must_change_password"] is True
        assert client.get("/api/archive-entries/", headers=headers).status_code == 403

        same = client.post("/api/auth/change-password", headers=headers, json={"new_password": "admin"})
        assert same.status_code == 422  # shorter than 8 characters
        changed = client.post("/api/auth/change-password", headers=headers, json={"new_password": "Fresh-pass-1"})
        assert changed.status_code == 200, changed.text

        headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
        assert client.get("/api/auth/me", headers=headers).json()["must_change_password"] is False
        assert client.get("/api/archive-entries/", headers=headers).status_code == 200
        assert client.get("/api/setup/status").json()["default_login"] is None
        # From now on the current password is required again.
        again = client.post("/api/auth/change-password", headers=headers, json={"new_password": "Other-pass-2"})
        assert again.status_code == 400


def test_creating_users_requires_an_administrator():
    response = client.post("/api/users/", json={"username": "x", "email": "x@example.com", "password": "Passw0rd!"})
    assert response.status_code == 401


def _admin_headers():
    tokens = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"}).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_deleted_user_loses_every_session():
    admin = _admin_headers()
    name = f"gone-{uuid.uuid4().hex[:8]}"
    user = client.post("/api/users/", headers=admin, json={"username": name, "email": f"{name}@example.com", "password": "Passw0rd!"}).json()
    tokens = client.post("/api/auth/login", json={"username": name, "password": "Passw0rd!"}).json()

    assert client.delete(f"/api/users/{user['id']}", headers=admin).status_code == 204
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_short_passwords_are_refused():
    response = client.post("/api/users/", headers=_admin_headers(), json={"username": "shorty", "email": "shorty@example.com", "password": "abc"})
    assert response.status_code == 422


def test_reset_password_script_restores_the_default_sign_in(monkeypatch):
    from scripts import reset_password

    name = f"locked-{uuid.uuid4().hex[:8]}"
    db = TestingSessionLocal()
    db.add(User(username=name, email=f"{name}@example.com", hashed_password=hash_password("Forgotten-1"), is_active=False))
    db.commit()
    db.close()

    monkeypatch.setattr(reset_password, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("sys.argv", ["reset_password", name])
    reset_password.main()

    tokens = client.post("/api/auth/login", json={"username": name, "password": settings.DEFAULT_ADMIN_PASSWORD}).json()
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}).json()
    assert me["must_change_password"] is True
