import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.models.archive_entry import ArchiveEntry
from app.schemas.metadata import MetadataDetails
from app.services.metadata import MetadataService
from app.utils.enums import MetadataStatus
from main import app
from tests.test_metadata import CatalogProvider
from tests.test_db import TestingSessionLocal

client = TestClient(app)


def _token(username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password}).json()["access_token"]


def _versions(suffix):
    db = TestingSessionLocal()
    try:
        entries = [
            ArchiveEntry(title=f"meadow {suffix}", file_path=f"/games/{suffix}-v1.zip", group_key=f"meadow{suffix}"),
            ArchiveEntry(title=f"meadow {suffix}", file_path=f"/games/{suffix}-v2.zip", group_key=f"meadow{suffix}"),
            ArchiveEntry(title=f"My meadow {suffix}", file_path=f"/games/{suffix}-v3.zip", group_key=f"meadow{suffix}",
                         metadata_override=True),
        ]
        db.add_all(entries)
        db.commit()
        return [entry.id for entry in entries]
    finally:
        db.close()


def test_identify_applies_the_match_to_every_unlocked_version():
    suffix = uuid.uuid4().hex[:8]
    first, second, locked = _versions(suffix)
    details = MetadataDetails(provider="VNDB", provider_id="v42", title="Quiet Meadow", developers=[f"Pond {suffix}"])

    with patch.object(MetadataService, "get_merged_details", return_value=details):
        response = client.post(
            f"/api/archive-entries/{first}/identify",
            headers={"Authorization": f"Bearer {_token('admin', 'Admin123!')}"},
            json={"provider": "VNDB", "provider_id": "v42"},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entry"]["title"] == "Quiet Meadow"
    assert body["updated_entries"] == 2
    assert body["artwork_job"]["job_type"] == "ARTWORK_REFRESH"

    db = TestingSessionLocal()
    try:
        for entry_id in (first, second):
            entry = db.get(ArchiveEntry, entry_id)
            assert (entry.metadata_source, entry.metadata_source_code, entry.metadata_status) == ("VNDB", "v42", MetadataStatus.MATCHED)
            assert [developer.name for developer in entry.developers] == [f"Pond {suffix}"]
        assert db.get(ArchiveEntry, locked).metadata_source_code is None
    finally:
        db.close()


def test_identify_requires_edit_metadata_and_a_real_record():
    suffix = uuid.uuid4().hex[:8]
    first, _, _ = _versions(suffix)
    url = f"/api/archive-entries/{first}/identify"
    payload = {"provider": "VNDB", "provider_id": "v0"}

    assert client.post(url, headers={"Authorization": f"Bearer {_token('testuser', 'Test123!')}"}, json=payload).status_code == 403
    with patch.object(MetadataService, "get_merged_details", return_value=None):
        response = client.post(url, headers={"Authorization": f"Bearer {_token('admin', 'Admin123!')}"}, json=payload)
    assert response.status_code == 404


def test_search_all_uses_enabled_providers_in_order():
    vn = MetadataDetails(provider="VNDB", provider_id="v1", title="Quiet Meadow")
    game = MetadataDetails(provider="IGDB", provider_id="7", title="Quiet Meadow")
    service = MetadataService(providers=[CatalogProvider("IGDB", 10, [game]), CatalogProvider("VNDB", 5, [vn])], provider_order=["VNDB", "IGDB"])
    db = TestingSessionLocal()
    try:
        assert [r.provider for r in service.search_providers(db, "meadow", "all")] == ["VNDB", "IGDB"]
        assert [r.provider for r in service.search_providers(db, "meadow", "IGDB")] == ["IGDB"]
        assert service.search_providers(db, "meadow", "Nope") == []
    finally:
        db.close()
