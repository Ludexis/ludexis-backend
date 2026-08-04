import uuid

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


def admin_headers():
    return {"Authorization": f"Bearer {admin_token()}"}


def create_collection(token):
    unique_name = f"test-collection-{uuid.uuid4().hex}"
    response = client.post(
        "/api/collections/",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": unique_name},
    )
    return response


INT_STAT_FIELDS = {
    "archive_entries",
    "collections",
    "tags",
    "developers",
    "publishers",
    "franchises",
    "users",
}
FLOAT_STAT_FIELDS = {
    "metadata_coverage",
    "verification_coverage",
}


def test_admin_stats_contains_all_expected_fields():
    response = client.get(
        "/api/admin/stats",
        headers=admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    for field in INT_STAT_FIELDS | FLOAT_STAT_FIELDS:
        assert field in payload, f"Missing AdminStats field: {field}"
    for field in INT_STAT_FIELDS:
        assert isinstance(payload[field], int), f"{field} should be an int"
    for field in FLOAT_STAT_FIELDS:
        assert isinstance(payload[field], (int, float)), f"{field} should be a number"


def test_admin_permission_report():
    response = client.get(
        "/api/admin/permission-report",
        headers=admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, dict)
    assert "Administrator" in payload
    permissions = payload["Administrator"]
    assert isinstance(permissions, list)
    assert len(permissions) > 0
    assert all(isinstance(permission, str) for permission in permissions)


def test_admin_audit_logs_filtered_by_entity():
    create_response = create_collection(admin_token())
    assert create_response.status_code == 201
    assert create_response.json()["id"]

    response = client.get(
        "/api/admin/audit-logs",
        headers=admin_headers(),
        params={"entity": "Collection"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert any(
        entry["entity"] == "Collection" for entry in payload
    ), "Expected an audit log entry with entity 'Collection'"


def test_admin_audit_logs_filtered_by_action():
    create_response = create_collection(admin_token())
    assert create_response.status_code == 201
    created_id = create_response.json()["id"]

    response = client.get(
        "/api/admin/audit-logs",
        headers=admin_headers(),
        params={"action": "create"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    if payload:
        assert all(
            entry["action"] == "create" for entry in payload
        ), "All filtered entries should have action 'create'"
    assert any(
        entry["action"] == "create" and entry["entity"] == "Collection"
        and entry["entity_id"] == created_id
        for entry in payload
    ), "Expected the created collection's audit log entry"


def test_admin_audit_logs_requires_view_permission():
    response = client.get(
        "/api/admin/audit-logs",
        headers={"Authorization": f"Bearer {user_token()}"},
    )
    assert response.status_code == 403


def test_admin_stats_requires_admin_permission():
    response = client.get(
        "/api/admin/stats",
        headers={"Authorization": f"Bearer {user_token()}"},
    )
    assert response.status_code == 403


def test_permission_report_requires_admin_permission():
    response = client.get(
        "/api/admin/permission-report",
        headers={"Authorization": f"Bearer {user_token()}"},
    )
    assert response.status_code == 403


def test_admin_stats_requires_authentication():
    response = client.get("/api/admin/stats")
    assert response.status_code == 401


def test_audit_logs_requires_authentication():
    response = client.get("/api/admin/audit-logs")
    assert response.status_code == 401


def test_permission_report_requires_authentication():
    response = client.get("/api/admin/permission-report")
    assert response.status_code == 401
