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


def _create_collection(token, name=None, **extra):
    payload = {"name": name or f"Collection-{uuid.uuid4().hex}"}
    payload.update(extra)
    return client.post("/api/collections/", headers=auth_headers(token), json=payload)


def test_create_collection():
    token = admin_token()
    name = f"Collection-{uuid.uuid4().hex}"
    response = _create_collection(token, name=name)
    assert response.status_code == 201
    data = response.json()
    assert data["id"]
    assert data["name"] == name
    assert data["entry_ids"] == []


def test_list_collections_contains_created():
    token = admin_token()
    created = _create_collection(token)
    assert created.status_code == 201
    collection_id = created.json()["id"]

    response = client.get("/api/collections/", headers=auth_headers(token))
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert collection_id in ids


def test_get_collection_by_id():
    token = admin_token()
    name = f"Collection-{uuid.uuid4().hex}"
    created = _create_collection(token, name=name)
    assert created.status_code == 201
    collection_id = created.json()["id"]

    response = client.get(f"/api/collections/{collection_id}", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["name"] == name


def test_get_nonexistent_collection():
    token = admin_token()
    missing_id = str(uuid.uuid4())
    response = client.get(f"/api/collections/{missing_id}", headers=auth_headers(token))
    assert response.status_code == 404


def test_patch_collection_updates_fields():
    token = admin_token()
    created = _create_collection(token)
    assert created.status_code == 201
    collection_id = created.json()["id"]

    new_name = f"Renamed-{uuid.uuid4().hex}"
    response = client.patch(
        f"/api/collections/{collection_id}",
        headers=auth_headers(token),
        json={"name": new_name, "visibility": "private"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new_name
    assert data["visibility"] == "private"


def _create_archive_entry(token):
    suffix = uuid.uuid4().hex
    response = client.post(
        "/api/archive-entries/",
        headers=auth_headers(token),
        json={
            "title": f"{suffix}-CollectionEntry",
            "file_path": f"D:/Tmp/{suffix}.zip",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_add_and_remove_entry_in_collection():
    token = admin_token()
    created = _create_collection(token)
    assert created.status_code == 201
    collection_id = created.json()["id"]

    entry_id = _create_archive_entry(token)

    add_response = client.post(
        f"/api/collections/{collection_id}/entries",
        headers=auth_headers(token),
        json={"entry_id": entry_id},
    )
    assert add_response.status_code == 200
    assert entry_id in add_response.json()["entry_ids"]

    remove_response = client.delete(
        f"/api/collections/{collection_id}/entries/{entry_id}",
        headers=auth_headers(token),
    )
    assert remove_response.status_code == 200
    assert entry_id not in remove_response.json()["entry_ids"]


def test_add_nonexistent_entry_returns_400():
    token = admin_token()
    created = _create_collection(token)
    assert created.status_code == 201
    collection_id = created.json()["id"]

    response = client.post(
        f"/api/collections/{collection_id}/entries",
        headers=auth_headers(token),
        json={"entry_id": str(uuid.uuid4())},
    )
    assert response.status_code == 400


def test_delete_collection():
    token = admin_token()
    created = _create_collection(token)
    assert created.status_code == 201
    collection_id = created.json()["id"]

    delete_response = client.delete(
        f"/api/collections/{collection_id}", headers=auth_headers(token)
    )
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/collections/{collection_id}", headers=auth_headers(token))
    assert get_response.status_code == 404


def test_rbac_collections():
    user = user_token()

    list_response = client.get("/api/collections/", headers=auth_headers(user))
    assert list_response.status_code == 200

    create_response = client.post(
        "/api/collections/",
        headers=auth_headers(user),
        json={"name": f"Forbidden-{uuid.uuid4().hex}"},
    )
    assert create_response.status_code == 403

    admin = admin_token()
    created = _create_collection(admin)
    assert created.status_code == 201
    collection_id = created.json()["id"]

    patch_response = client.patch(
        f"/api/collections/{collection_id}",
        headers=auth_headers(user),
        json={"name": "Hijack"},
    )
    assert patch_response.status_code == 403

    delete_response = client.delete(
        f"/api/collections/{collection_id}", headers=auth_headers(user)
    )
    assert delete_response.status_code == 403

    unauthenticated = client.post(
        "/api/collections/", json={"name": f"Anon-{uuid.uuid4().hex}"}
    )
    assert unauthenticated.status_code == 401
