import base64
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.models.archive_entry import ArchiveEntry
from app.models.franchise import Franchise
from app.services.artwork import ArtworkService
from app.services.storage import StorageService
from app.utils.enums import MetadataStatus
from main import app
from tests.test_db import TestingSessionLocal

client = TestClient(app)
storage = StorageService()

PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def headers(username="admin", password="Admin123!"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(autouse=True)
def no_steamgriddb():
    with patch("app.services.franchise.SettingsService.steamgriddb_key", return_value=None):
        yield


@pytest.fixture
def franchise():
    """A franchise with an older and a newer game, each with a stored banner, and one game without art."""
    db = TestingSessionLocal()
    item = Franchise(name=f"Skybound {uuid.uuid4().hex[:8]}")
    db.add(item)
    db.flush()
    banners = {}
    for title, released in (("Second", date(2012, 1, 1)), ("First", date(2004, 1, 1)), ("Unreleased", None)):
        path = None if released is None else storage.save(f"banners/{uuid.uuid4().hex}.png", PNG_BYTES)
        banners[title] = path
        db.add(ArchiveEntry(
            title=f"{item.name} {title}", file_path=f"D:/Tmp/{uuid.uuid4()}.zip", franchise_id=item.id,
            release_date=released, banner_path=path, metadata_status=MetadataStatus.MATCHED,
        ))
    db.commit()
    yield item.id, banners
    db.close()


def test_a_franchise_shows_its_first_released_games_banner(franchise):
    franchise_id, banners = franchise
    body = client.get(f"/api/franchises/{franchise_id}", headers=headers()).json()

    assert body["banner_path"] is None
    assert body["image_path"] == banners["First"]
    assert body["entry_count"] == 3


def test_choosing_a_games_banner_copies_it_for_the_franchise(franchise):
    franchise_id, banners = franchise
    auth = headers()
    candidates = client.get(f"/api/franchises/{franchise_id}/image-candidates", headers=auth).json()
    assert candidates == [banners["First"], banners["Second"]]

    body = client.put(f"/api/franchises/{franchise_id}/image", headers=auth, json={"source": banners["Second"]}).json()

    assert body["banner_path"].startswith(f"franchises/{franchise_id}/")
    assert body["image_path"] == body["banner_path"]
    assert storage.absolute_path(body["banner_path"]).read_bytes() == storage.absolute_path(banners["Second"]).read_bytes()
    # Unused-file cleanup keeps the franchise's own copy.
    ArtworkService().garbage_collect_artwork(TestingSessionLocal())
    assert storage.exists(body["banner_path"])


def test_only_offered_images_can_be_chosen(franchise):
    franchise_id, _ = franchise
    response = client.put(f"/api/franchises/{franchise_id}/image", headers=headers(), json={"source": "covers/other-game.png"})

    assert response.status_code == 400


def test_uploading_then_resetting_returns_to_the_automatic_image(franchise):
    franchise_id, banners = franchise
    auth = headers()
    uploaded = client.post(
        f"/api/franchises/{franchise_id}/image", headers=auth, files={"file": ("art.png", PNG_BYTES, "image/png")},
    ).json()
    assert uploaded["banner_path"].endswith(".webp")

    reset = client.delete(f"/api/franchises/{franchise_id}/image", headers=auth).json()

    assert reset["banner_path"] is None
    assert reset["image_path"] == banners["First"]
    assert not storage.exists(uploaded["banner_path"])


def test_a_user_without_edit_rights_cannot_change_the_image(franchise):
    franchise_id, banners = franchise
    response = client.put(
        f"/api/franchises/{franchise_id}/image", headers=headers("testuser", "Test123!"), json={"source": banners["First"]},
    )

    assert response.status_code == 403
