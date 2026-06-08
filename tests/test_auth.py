from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

USERNAME = "admin"
PASSWORD = "adminpassword"


def login():
    response = client.post(
        "/api/auth/login",
        json={
            "username": USERNAME,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_login_success():
    response = client.post(
        "/api/auth/login",
        json={
            "username": USERNAME,
            "password": PASSWORD,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password():
    response = client.post(
        "/api/auth/login",
        json={
            "username": USERNAME,
            "password": "WrongPassword",
        },
    )
    assert response.status_code == 401


def test_read_current_user():
    token = login()["access_token"]
    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == USERNAME


def test_me_requires_auth():
    response = client.get(
        "/api/auth/me",
    )
    assert response.status_code == 401


def test_refresh_token():
    refresh_token = login()["refresh_token"]
    response = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_refresh_token_cannot_be_reused():
    refresh_token = login()["refresh_token"]
    first_refresh = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert first_refresh.status_code == 200
    second_refresh = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert second_refresh.status_code == 401


def test_logout_revokes_token():
    refresh_token = login()["refresh_token"]
    logout_response = client.post(
        "/api/auth/logout",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert logout_response.status_code == 204
    refresh_response = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert refresh_response.status_code == 401


def test_invalid_refresh_token():
    response = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": "this-is-not-a-valid-token",
        },
    )
    assert response.status_code == 401