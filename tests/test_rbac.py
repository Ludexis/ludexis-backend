from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def admin_token():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin123!",
        },
    )
    return response.json()["access_token"]


def user_token():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "testuser",
            "password": "Test123!",
        },
    )
    return response.json()["access_token"]


def test_admin_can_run_scan():
    token = admin_token()
    response = client.post(
        "/api/scan/full",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 201


def test_scan_requires_auth():
    response = client.post(
        "/api/scan/full"
    )
    assert response.status_code == 401


def test_user_cannot_run_scan():
    token = user_token()
    response = client.post(
        "/api/scan/full",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 403


def test_user_can_access_me():
    token = user_token()
    response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 200


def test_admin_can_view_jobs():
    token = admin_token()
    response = client.get(
        "/api/jobs",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 200


def test_user_can_view_jobs():
    token = user_token()
    response = client.get(
        "/api/jobs",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 200