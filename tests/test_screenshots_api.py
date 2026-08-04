import base64
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from main import app

from app.models.archive_entry import ArchiveEntry
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult
from app.services.metadata import MetadataService
from tests.test_db import TestingSessionLocal

client = TestClient(app)

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def admin_token():
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def user_token():
    response = client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "Test123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _unique():
    return uuid.uuid4().hex


def _create_entry(token, title, file_path):
    response = client.post(
        "/api/archive-entries/",
        headers=_auth_headers(token),
        json={"title": title, "file_path": file_path},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_screenshot(token, entry_id, caption="In-game screenshot"):
    return client.post(
        "/api/artwork/upload",
        headers=_auth_headers(token),
        files={"file": ("screenshot.png", PNG_BYTES, "image/png")},
        data={"archive_entry_id": entry_id, "artwork_type": "screenshot", "caption": caption},
    )


def test_screenshots_empty_for_entry():
    token = admin_token()
    entry_id = _create_entry(token, f"Screenshots Empty {_unique()}", f"C:/archives/empty-{_unique()}.iso")
    response = client.get(
        f"/api/archive-entries/{entry_id}/screenshots",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json() == []


def test_upload_screenshot_and_list():
    token = admin_token()
    entry_id = _create_entry(token, f"Screenshot Upload {_unique()}", f"C:/archives/upload-{_unique()}.iso")
    upload = _upload_screenshot(token, entry_id)
    assert upload.status_code == 201, upload.text
    uploaded = upload.json()
    assert uploaded["screenshot_id"]
    response = client.get(
        f"/api/archive-entries/{entry_id}/screenshots",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    screenshots = response.json()
    assert len(screenshots) == 1
    shot = screenshots[0]
    assert shot["id"] == uploaded["screenshot_id"]
    assert shot["archive_entry_id"] == entry_id
    assert shot["file_path"]
    assert shot["created_at"]


def test_screenshots_nonexistent_entry_404():
    token = admin_token()
    response = client.get(
        f"/api/archive-entries/{uuid.uuid4()}/screenshots",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_delete_screenshot_empties_list():
    token = admin_token()
    entry_id = _create_entry(token, f"Screenshot Delete {_unique()}", f"C:/archives/delete-shot-{_unique()}.iso")
    upload = _upload_screenshot(token, entry_id)
    assert upload.status_code == 201, upload.text
    screenshot_id = upload.json()["screenshot_id"]
    delete_response = client.delete(
        f"/api/artwork/{screenshot_id}",
        headers=_auth_headers(token),
        params={"artwork_type": "screenshot"},
    )
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["deleted"] is True
    response = client.get(
        f"/api/archive-entries/{entry_id}/screenshots",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json() == []


def test_user_cannot_upload_screenshot():
    entry_id = _create_entry(admin_token(), f"Screenshot RBAC {_unique()}", f"C:/archives/rbac-shot-{_unique()}.iso")
    response = _upload_screenshot(user_token(), entry_id)
    assert response.status_code == 403, response.text


def test_metadata_confidence_null_without_auto_match():
    token = admin_token()
    entry_id = _create_entry(token, f"Confidence Null {_unique()}", f"C:/archives/conf-null-{_unique()}.iso")
    response = client.get(
        f"/api/archive-entries/{entry_id}",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert "metadata_confidence" in body
    assert body["metadata_confidence"] is None


class FakeProvider(MetadataProvider):
    name = "Fake"
    priority = 1

    def search(self, query, limit=20):
        return [
            MetadataSearchResult(
                provider="Fake",
                provider_id="1",
                title="Portal 2",
                summary="Test",
            )
        ]

    def get_details(self, external_id):
        return MetadataDetails(
            provider="Fake",
            provider_id="1",
            title="Portal 2",
            description="Test Game",
            genres=[],
            developers=[],
            publishers=[],
            tags=[],
            cover_urls=[],
            banner_urls=[],
            logo_urls=[],
            artwork_urls=[],
        )

    def download_artwork(self, external_id):
        return None


def test_metadata_confidence_persisted_after_auto_match():
    token = admin_token()
    entry_id = _create_entry(token, f"Confidence Match {_unique()}", f"C:/archives/conf-match-{_unique()}.iso")
    result = MetadataSearchResult(
        provider="Fake",
        provider_id="1",
        title="Portal 2",
        summary="Test",
    )
    service = MetadataService(providers=[FakeProvider()])
    db = TestingSessionLocal()
    try:
        archive = db.query(ArchiveEntry).filter(ArchiveEntry.id == entry_id).first()
        with patch.object(MetadataService, "auto_match", return_value=(result, 0.87)):
            service.auto_match_archive(db, archive)
    finally:
        db.close()
    response = client.get(
        f"/api/archive-entries/{entry_id}",
        headers=_auth_headers(token),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["metadata_confidence"] == round(0.87, 3)
