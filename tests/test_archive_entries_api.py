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


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _unique():
    return uuid.uuid4().hex


def _create_entry(token, title, file_path, file_hash=None):
    payload = {"title": title, "file_path": file_path}
    if file_hash is not None:
        payload["file_hash"] = file_hash
    response = client.post(
        "/api/archive-entries/",
        headers=_auth(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_archive_entry():
    token = admin_token()
    suffix = _unique()
    title = f"Created Entry {suffix}"
    file_path = f"C:/archives/created-{suffix}.iso"
    data = _create_entry(token, title, file_path)
    assert data["id"]
    assert data["metadata_status"] == "UNMATCHED"
    assert data["title"] == title
    assert data["file_path"] == file_path


def test_get_archive_entry_by_id():
    token = admin_token()
    data = _create_entry(token, f"Get By Id {_unique()}", f"C:/archives/get-{_unique()}.iso")
    response = client.get(
        f"/api/archive-entries/{data['id']}",
        headers=_auth(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == data["id"]
    assert body["title"] == data["title"]


def test_get_archive_entry_not_found():
    token = admin_token()
    response = client.get(
        f"/api/archive-entries/{uuid.uuid4()}",
        headers=_auth(token),
    )
    assert response.status_code == 404


def test_patch_archive_entry():
    token = admin_token()
    data = _create_entry(token, f"Patch Entry {_unique()}", f"C:/archives/patch-{_unique()}.iso")
    new_title = f"Patched Title {_unique()}"
    new_description = "Patched description"
    response = client.patch(
        f"/api/archive-entries/{data['id']}",
        headers=_auth(token),
        json={
            "title": new_title,
            "description": new_description,
            "file_path": data["file_path"],
            "metadata_status": data["metadata_status"],
            "verification_status": data["verification_status"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == new_title
    assert body["description"] == new_description
    assert body["id"] == data["id"]


def test_override_metadata():
    token = admin_token()
    data = _create_entry(token, f"Override Entry {_unique()}", f"C:/archives/override-{_unique()}.iso")
    new_title = f"Overridden Title {_unique()}"
    new_description = "Overridden description"
    response = client.patch(
        f"/api/archive-entries/{data['id']}/metadata",
        headers=_auth(token),
        json={
            "title": new_title,
            "description": new_description,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == new_title
    assert body["description"] == new_description
    assert body["metadata_override"] is True
    assert body["metadata_status"] == "MANUAL"


def test_duplicates():
    token = admin_token()
    file_hash = "0" * 64
    first = _create_entry(token, f"Duplicate A {_unique()}", f"C:/archives/dup-a-{_unique()}.iso", file_hash=file_hash)
    second = _create_entry(token, f"Duplicate B {_unique()}", f"C:/archives/dup-b-{_unique()}.iso", file_hash=file_hash)
    response = client.get(
        "/api/archive-entries/duplicates",
        headers=_auth(token),
    )
    assert response.status_code == 200
    groups = response.json()
    assert isinstance(groups, list)
    matching = [
        group
        for group in groups
        if any(entry["id"] == first["id"] for entry in group["entries"])
        and any(entry["id"] == second["id"] for entry in group["entries"])
    ]
    assert matching, "No duplicate group contains both created entries"
    group = matching[0]
    assert group["file_hash"] == file_hash
    assert group["count"] >= 2
    entry_ids = {entry["id"] for entry in group["entries"]}
    assert first["id"] in entry_ids
    assert second["id"] in entry_ids


def test_delete_archive_entry():
    token = admin_token()
    data = _create_entry(token, f"Delete Entry {_unique()}", f"C:/archives/delete-{_unique()}.iso")
    delete_response = client.delete(
        f"/api/archive-entries/{data['id']}",
        headers=_auth(token),
    )
    assert delete_response.status_code == 204
    get_response = client.get(
        f"/api/archive-entries/{data['id']}",
        headers=_auth(token),
    )
    assert get_response.status_code == 404


def test_rbac_archive_entries():
    admin = admin_token()
    user = user_token()

    forbidden_post = client.post(
        "/api/archive-entries/",
        headers=_auth(user),
        json={
            "title": f"Forbidden Entry {_unique()}",
            "file_path": f"C:/archives/forbidden-{_unique()}.iso",
        },
    )
    assert forbidden_post.status_code == 403

    target = _create_entry(admin, f"RBAC Target {_unique()}", f"C:/archives/rbac-{_unique()}.iso")

    forbidden_patch = client.patch(
        f"/api/archive-entries/{target['id']}",
        headers=_auth(user),
        json={"title": "No"},
    )
    assert forbidden_patch.status_code == 403

    forbidden_delete = client.delete(
        f"/api/archive-entries/{target['id']}",
        headers=_auth(user),
    )
    assert forbidden_delete.status_code == 403

    list_response = client.get(
        "/api/archive-entries/",
        headers=_auth(user),
    )
    assert list_response.status_code == 200


def test_unauthenticated_create_archive_entry():
    response = client.post(
        "/api/archive-entries/",
        json={
            "title": f"Anonymous Entry {_unique()}",
            "file_path": f"C:/archives/anonymous-{_unique()}.iso",
        },
    )
    assert response.status_code == 401
