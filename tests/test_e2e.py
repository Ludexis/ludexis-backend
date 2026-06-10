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
    assert response.status_code == 200
    return response.json()["access_token"]


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


def test_authentication_journey():
    login_response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin123!",
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.json()["refresh_token"]
    me_response = client.get(
        "/api/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"
    refresh_response = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert refresh_response.status_code == 200
    logout_response = client.post(
        "/api/auth/logout",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert logout_response.status_code == 204
    reused_refresh = client.post(
        "/api/auth/refresh",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert reused_refresh.status_code == 401


def test_rbac_library_creation_journey():
    admin = admin_token()
    create_library = client.post(
        "/api/libraries",
        headers={
            "Authorization": f"Bearer {admin}"
        },
        json={
            "name": "E2E Library",
            "path": "E:/E2E",
            "enabled": True,
        },
    )
    assert create_library.status_code in [200, 201]
    user = user_token()
    forbidden_create = client.post(
        "/api/libraries",
        headers={
            "Authorization": f"Bearer {user}"
        },
        json={
            "name": "Forbidden Library",
            "path": "E:/Forbidden",
            "enabled": True,
        },
    )
    assert forbidden_create.status_code == 403


def test_scan_job_journey():
    token = admin_token()
    scan_response = client.post(
        "/api/scan/full",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert scan_response.status_code in [200, 201]
    job_id = scan_response.json()["id"]
    job_response = client.get(
        f"/api/jobs/{job_id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert job_response.status_code == 200
    jobs_response = client.get(
        "/api/jobs",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert jobs_response.status_code == 200
    status_response = client.get(
        "/api/scan/status",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )
    assert status_response.status_code == 200


def test_search_journey():
    token = user_token()
    response = client.get(
        "/api/search",
        headers={
            "Authorization": f"Bearer {token}"
        },
        params={
            "query": "test",
        },
    )
    assert response.status_code == 200

def test_admin_workflow():
    login_response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin123!",
        },
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]
    refresh_token = login_response.json()["refresh_token"]
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    library_response = client.post(
        "/api/libraries",
        headers=headers,
        json={
            "name": "Admin Workflow Library",
            "path": "E:/AdminWorkflow",
            "enabled": True,
        },
    )
    assert library_response.status_code in [200, 201]

    scan_response = client.post(
        "/api/scan/full",
        headers=headers,
    )
    assert scan_response.status_code in [200, 201]
    job_id = scan_response.json()["id"]
    job_response = client.get(
        f"/api/jobs/{job_id}",
        headers=headers,
    )
    assert job_response.status_code == 200
    jobs_response = client.get(
        "/api/jobs",
        headers=headers,
    )
    assert jobs_response.status_code == 200
    logout_response = client.post(
        "/api/auth/logout",
        json={
            "refresh_token": refresh_token,
        },
    )
    assert logout_response.status_code == 204