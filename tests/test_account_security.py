import uuid

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.models.user import User
from main import app
from tests.test_db import TestingSessionLocal

client = TestClient(app)
CSRF = {"X-Requested-With": "ludexis"}


def make_user(password="Old-pass-1"):
    db = TestingSessionLocal()
    try:
        name = f"reader-{uuid.uuid4().hex[:8]}"
        db.add(User(username=name, email=f"{name}@example.com", hashed_password=hash_password(password)))
        db.commit()
        return name
    finally:
        db.close()


def login(username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password}).json()


def bearer(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_change_password_signs_out_other_sessions():
    name = make_user()
    this_device = login(name, "Old-pass-1")
    other_device = login(name, "Old-pass-1")

    response = client.post(
        "/api/auth/change-password", headers=bearer(this_device),
        json={"current_password": "Old-pass-1", "new_password": "New-pass-22"},
    )
    assert response.status_code == 200, response.text
    fresh = response.json()

    assert client.get("/api/auth/me", headers=bearer(fresh)).status_code == 200
    assert client.get("/api/auth/me", headers=bearer(other_device)).status_code == 401
    assert client.post("/api/auth/refresh", json={"refresh_token": other_device["refresh_token"]}).status_code == 401
    assert client.post("/api/auth/login", json={"username": name, "password": "Old-pass-1"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": name, "password": "New-pass-22"}).status_code == 200


def test_change_password_checks_the_current_password_and_length():
    name = make_user()
    tokens = login(name, "Old-pass-1")
    url = "/api/auth/change-password"

    assert client.post(url, headers=bearer(tokens), json={"current_password": "wrong", "new_password": "New-pass-22"}).status_code == 400
    assert client.post(url, headers=bearer(tokens), json={"current_password": "Old-pass-1", "new_password": "short"}).status_code == 422
    for _ in range(4):
        client.post(url, headers=bearer(tokens), json={"current_password": "wrong", "new_password": "New-pass-22"})
    blocked = client.post(url, headers=bearer(tokens), json={"current_password": "Old-pass-1", "new_password": "New-pass-22"})
    assert blocked.status_code == 429


def test_cookie_password_change_renews_cookies_without_exposing_tokens():
    name = make_user()
    tokens = login(name, "Old-pass-1")
    response = client.post(
        "/api/auth/change-password", headers={"Cookie": f"ludexis_access={tokens['access_token']}", **CSRF},
        json={"current_password": "Old-pass-1", "new_password": "New-pass-22"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"] is None
    assert any(c.startswith("ludexis_access=") for c in response.headers.get_list("set-cookie"))


def test_logout_all_ends_every_session():
    name = make_user()
    first, second = login(name, "Old-pass-1"), login(name, "Old-pass-1")

    response = client.post("/api/auth/logout-all", headers=bearer(first))
    assert response.status_code == 204
    assert any(c.startswith('ludexis_access=""') for c in response.headers.get_list("set-cookie"))
    for tokens in (first, second):
        assert client.get("/api/auth/me", headers=bearer(tokens)).status_code == 401
        assert client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401
    # Signing in again works.
    assert client.get("/api/auth/me", headers=bearer(login(name, "Old-pass-1"))).status_code == 200
