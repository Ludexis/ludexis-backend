from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def user_token():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "testuser",
            "password": "Test123!",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_run_scans_permission_required():
    token = user_token()
    response = client.post(
        "/api/scan/full",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 403


def test_manage_users_permission_required():
    token = user_token()
    response = client.get(
        "/api/users",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 403


def test_access_admin_permission_required():
    token = user_token()
    response = client.get(
        "/api/admin/stats",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 403


def test_view_audit_logs_permission_required():
    token = user_token()
    response = client.get(
        "/api/admin/audit-logs",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert response.status_code == 403


def test_manage_collections_permission_required():
    token = user_token()
    response = client.post(
        "/api/collections",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "Test Collection"
        },
    )
    assert response.status_code == 403


def test_edit_metadata_permission_required():
    token = user_token()
    response = client.post(
        "/api/tags",
        headers={
            "Authorization": f"Bearer {token}"
        },
        json={
            "name": "TestTag"
        },
    )
    assert response.status_code == 403