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


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_library(token, name=None, **extra):
    suffix = uuid.uuid4().hex
    payload = {"name": name or f"Library-{suffix}", "path": f"D:/Tmp/{suffix}"}
    payload.update(extra)
    return client.post("/api/libraries/", headers=auth_headers(token), json=payload)


def test_create_library():
    token = admin_token()
    name = f"Library-{uuid.uuid4().hex}"
    response = _create_library(token, name=name, enabled=True)
    assert response.status_code == 201
    data = response.json()
    assert data["id"]
    assert data["name"] == name
    assert data["path"]
    assert data["enabled"] is True


def test_list_libraries_contains_created():
    token = admin_token()
    created = _create_library(token)
    assert created.status_code == 201
    library_id = created.json()["id"]

    response = client.get("/api/libraries/", headers=auth_headers(token))
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert library_id in ids


def test_get_library_by_id():
    token = admin_token()
    name = f"Library-{uuid.uuid4().hex}"
    created = _create_library(token, name=name)
    assert created.status_code == 201
    library_id = created.json()["id"]

    response = client.get(f"/api/libraries/{library_id}", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["name"] == name


def test_get_nonexistent_library():
    token = admin_token()
    missing_id = str(uuid.uuid4())
    response = client.get(f"/api/libraries/{missing_id}", headers=auth_headers(token))
    assert response.status_code == 404


def test_patch_library_updates_fields():
    token = admin_token()
    created = _create_library(token)
    assert created.status_code == 201
    library_id = created.json()["id"]

    response = client.patch(
        f"/api/libraries/{library_id}",
        headers=auth_headers(token),
        json={"enabled": False, "name": f"Renamed-{uuid.uuid4().hex}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == library_id
    assert data["enabled"] is False


def test_create_library_with_duplicate_name_returns_400():
    token = admin_token()
    name = f"Duplicate-{uuid.uuid4().hex}"
    created = _create_library(token, name=name)
    assert created.status_code == 201

    response = _create_library(token, name=name)
    assert response.status_code == 400


def test_delete_library():
    token = admin_token()
    created = _create_library(token)
    assert created.status_code == 201
    library_id = created.json()["id"]

    delete_response = client.delete(
        f"/api/libraries/{library_id}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/libraries/{library_id}", headers=auth_headers(token))
    assert get_response.status_code == 404


def test_rbac_libraries():
    user = user_token()

    list_response = client.get("/api/libraries/", headers=auth_headers(user))
    assert list_response.status_code == 200

    admin = admin_token()
    created = _create_library(admin)
    assert created.status_code == 201
    library_id = created.json()["id"]

    patch_response = client.patch(
        f"/api/libraries/{library_id}",
        headers=auth_headers(user),
        json={"enabled": False},
    )
    assert patch_response.status_code == 403

    delete_response = client.delete(
        f"/api/libraries/{library_id}", headers=auth_headers(user)
    )
    assert delete_response.status_code == 403

    unauthenticated = client.get("/api/libraries/")
    assert unauthenticated.status_code == 401
