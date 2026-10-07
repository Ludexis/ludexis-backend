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


def test_auto_download_queues_a_job():
    response = client.post("/api/artwork/auto-download", headers=_auth_headers(admin_token()))
    assert response.status_code == 202, response.text
    assert response.json()["job_type"] == "ARTWORK_REFRESH"


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


def test_media_requires_a_session():
    from main import media_dir

    name = f"media-test-{uuid.uuid4().hex}.png"
    (media_dir / name).write_bytes(PNG_BYTES)
    try:
        access_token = admin_token()
        assert client.get(f"/media/{name}").status_code == 401
        # Tokens in the URL are not accepted; images authenticate with the session cookie.
        assert client.get(f"/media/{name}?media_token={access_token}").status_code == 401

        response = client.get(f"/media/{name}", headers={"Cookie": f"ludexis_access={access_token}"})
        assert response.status_code == 200
        assert response.content == PNG_BYTES
        assert client.get(f"/media/{name}", headers={"Authorization": f"Bearer {access_token}"}).status_code == 200
    finally:
        (media_dir / name).unlink()


def test_artwork_candidates_and_set_from_url():
    from unittest.mock import patch

    from app.schemas.metadata import MetadataDetails
    from app.services.artwork import ArtworkService

    token = admin_token()
    entry_id = _create_entry(token)
    details = MetadataDetails(
        provider="Steam", provider_id="1", title="x",
        cover_urls=["https://img.example/cover.jpg"], banner_urls=["https://img.example/hero.jpg"],
        artwork_urls=["https://img.example/shot.jpg"],
    )
    with patch.object(ArtworkService, "_entry_details", return_value=details), \
            patch.object(ArtworkService, "_download_artwork_url", return_value=(PNG_BYTES, ".png")):
        banners = client.get(f"/api/artwork/{entry_id}/candidates", headers=_auth_headers(token), params={"artwork_type": "banner"})
        assert banners.json() == ["https://img.example/hero.jpg", "https://img.example/cover.jpg", "https://img.example/shot.jpg"]

        chosen = client.post("/api/artwork/from-url", headers=_auth_headers(token), json={
            "archive_entry_id": entry_id, "artwork_type": "banner", "url": "https://img.example/shot.jpg",
        })
        assert chosen.status_code == 200, chosen.text
        assert chosen.json()["file_path"].endswith(".png")

        # Anything not offered for this game is refused rather than fetched.
        refused = client.post("/api/artwork/from-url", headers=_auth_headers(token), json={
            "archive_entry_id": entry_id, "artwork_type": "banner", "url": "http://169.254.169.254/latest",
        })
        assert refused.status_code == 400

    entry = client.get(f"/api/archive-entries/{entry_id}", headers=_auth_headers(token)).json()
    assert entry["banner_path"] == chosen.json()["file_path"]
