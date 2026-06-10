from datetime import datetime, UTC, timedelta

from fastapi.testclient import TestClient
from jose import jwt

from main import app
from app.core.config import settings

client = TestClient(app)


def create_expired_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "access",
        "exp": datetime.now(UTC) - timedelta(minutes=5),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_expired_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(UTC) - timedelta(days=1),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def get_admin_user_id() -> str:
    response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin123!",
        },
    )

    access_token = response.json()["access_token"]

    me = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    return me.json()["id"]


def test_expired_access_token_rejected():
    user_id = get_admin_user_id()

    token = create_expired_access_token(user_id)

    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401


def test_expired_refresh_token_rejected():
    user_id = get_admin_user_id()

    token = create_expired_refresh_token(user_id)

    response = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": token,
        },
    )

    assert response.status_code == 401