import base64
import uuid

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def admin_token():
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123!"},
    )
    return response.json()["access_token"]


def user_token():
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "Test123!"},
    )
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_entry(token):
    suffix = uuid.uuid4()
    response = client.post(
        "/api/archive-entries/",
        headers=_auth_headers(token),
        json={"title": str(suffix), "file_path": f"D:/Tmp/{suffix}.zip"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_cover(token, entry_id, filename="cover.png", content_type="image/png"):
    return client.post(
        "/api/artwork/upload",
        headers=_auth_headers(token),
        files={"file": (filename, PNG_BYTES, content_type)},
        data={"archive_entry_id": entry_id, "artwork_type": "cover"},
    )


def _delete_cover(token, entry_id):
    return client.delete(
        f"/api/artwork/{entry_id}",
        headers=_auth_headers(token),
        params={"artwork_type": "cover"},
    )


def test_create_archive_entry():
    entry_id = _create_entry(admin_token())
    assert isinstance(entry_id, str)
    assert entry_id


def test_upload_cover():
    entry_id = _create_entry(admin_token())
    response = _upload_cover(admin_token(), entry_id)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["archive_entry_id"] == entry_id
    assert data["artwork_type"] == "cover"
    assert data["file_path"]


def test_list_missing_artwork():
    _create_entry(admin_token())
    response = client.get(
        "/api/artwork/missing",
        headers=_auth_headers(admin_token()),
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_replace_artwork():
    entry_id = _create_entry(admin_token())
    _upload_cover(admin_token(), entry_id)
    response = client.patch(
        "/api/artwork/replace",
        headers=_auth_headers(admin_token()),
        files={"file": ("cover2.png", PNG_BYTES, "image/png")},
        data={"archive_entry_id": entry_id, "artwork_type": "cover"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["archive_entry_id"] == entry_id
    assert data["artwork_type"] == "cover"
    assert data["file_path"]


def test_upload_wrong_mime_type_returns_400():
    entry_id = _create_entry(admin_token())
    response = _upload_cover(
        admin_token(),
        entry_id,
        filename="note.txt",
        content_type="text/plain",
    )
    assert response.status_code == 400, response.text


def test_upload_nonexistent_entry_returns_400():
    response = _upload_cover(admin_token(), str(uuid.uuid4()))
    assert response.status_code == 400, response.text


def test_delete_artwork():
    entry_id = _create_entry(admin_token())
    _upload_cover(admin_token(), entry_id)
    response = _delete_cover(admin_token(), entry_id)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["deleted"] is True
    assert data["artwork_type"] == "cover"


def test_user_cannot_upload_artwork():
    entry_id = _create_entry(admin_token())
    response = _upload_cover(user_token(), entry_id)
    assert response.status_code == 403, response.text


def test_user_cannot_delete_artwork():
    entry_id = _create_entry(admin_token())
    response = _delete_cover(user_token(), entry_id)
    assert response.status_code == 403, response.text


def test_user_cannot_auto_download_artwork():
    response = client.post(
        "/api/artwork/auto-download",
        headers=_auth_headers(user_token()),
    )
    assert response.status_code == 403, response.text


def test_user_can_list_missing_artwork():
    response = client.get(
        "/api/artwork/missing",
        headers=_auth_headers(user_token()),
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_unauthenticated_upload_returns_401():
    entry_id = _create_entry(admin_token())
    response = client.post(
        "/api/artwork/upload",
        files={"file": ("cover.png", PNG_BYTES, "image/png")},
        data={"archive_entry_id": entry_id, "artwork_type": "cover"},
    )
    assert response.status_code == 401, response.text
