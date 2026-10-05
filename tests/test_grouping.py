import uuid

import pytest
import sqlalchemy as sa

from app.models.archive_entry import ArchiveEntry
from app.models.association_tables import archive_entry_relations
from app.models.collection import Collection
from app.services.grouping import version_order
from app.services.metadata import MetadataService
from app.services.scanner import ScannerService
from app.utils.enums import MetadataStatus, RelationshipType
from tests.test_db import TestingSessionLocal


def unique_word() -> str:
    # Letters only, so the shared test database never groups entries from different tests.
    return "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex[:10]).capitalize()


def entries_for(db, root) -> list[ArchiveEntry]:
    return db.query(ArchiveEntry).filter(ArchiveEntry.file_path.startswith(str(root.resolve()), autoescape=True)).all()


@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


def test_version_order():
    assert version_order("1.10") > version_order("1.9")
    assert version_order("1.0e") > version_order("1.0")
    assert version_order("0.2") > version_order(None)


def test_versions_share_a_group_with_the_newest_primary(db, tmp_path):
    name = unique_word()
    for version in ("0.9", "0.10", "0.2"):
        (tmp_path / f"{name} v{version}.zip").write_bytes(uuid.uuid4().bytes)
    result = ScannerService().scan_full(db, scan_root=str(tmp_path))

    entries = entries_for(db, tmp_path)
    assert len({entry.group_key for entry in entries}) == 1
    assert [entry.version for entry in entries if entry.is_primary_version] == ["0.10"]
    assert result["version_groups"] >= 1


def test_episodes_gather_into_an_auto_collection(db, tmp_path):
    series = unique_word()
    for episode in (1, 2, 3):
        (tmp_path / f"{series} Ep {episode} v1.0.zip").write_bytes(uuid.uuid4().bytes)
    ScannerService().scan_full(db, scan_root=str(tmp_path))

    entries = entries_for(db, tmp_path)
    assert sorted(entry.episode for entry in entries) == [1, 2, 3]
    assert all(entry.is_primary_version for entry in entries)
    collection = db.query(Collection).filter(Collection.auto_key == entries[0].series_key).one()
    assert collection.name == series
    assert {entry.id for entry in collection.archive_entries} == {entry.id for entry in entries}

    # A rescan reuses the collection instead of making another.
    ScannerService().scan_full(db, scan_root=str(tmp_path))
    assert db.query(Collection).filter(Collection.auto_key == entries[0].series_key).count() == 1

    # Each episode points at the next one, and a rescan does not duplicate the links.
    by_episode = {entry.episode: entry.id for entry in entries}
    links = db.execute(
        sa.select(archive_entry_relations.c.source_entry_id, archive_entry_relations.c.target_entry_id)
        .where(archive_entry_relations.c.relationship_type == RelationshipType.EPISODE,
               archive_entry_relations.c.source_entry_id.in_(by_episode.values()))
    ).all()
    assert sorted(links) == sorted([(by_episode[1], by_episode[2]), (by_episode[2], by_episode[3])])


def test_versions_of_one_episode_are_not_a_series(db, tmp_path):
    series = unique_word()
    for version in ("1.0", "1.1"):
        (tmp_path / f"{series} Ep 1 v{version}.zip").write_bytes(uuid.uuid4().bytes)
    ScannerService().scan_full(db, scan_root=str(tmp_path))

    key = entries_for(db, tmp_path)[0].series_key
    assert db.query(Collection).filter(Collection.auto_key == key).count() == 0


class CountingMetadataService(MetadataService):
    def __init__(self):
        super().__init__(providers=[])
        self.searches = 0
        self.refreshed = []

    def auto_match(self, title):
        self.searches += 1
        return None, 0.0

    def refresh_archive(self, db, archive):
        self.refreshed.append(archive.id)
        return True


def test_a_new_version_reuses_its_matched_sibling(db, tmp_path):
    name = unique_word()
    for version in ("1.0", "2.0"):
        (tmp_path / f"{name} v{version}.zip").write_bytes(uuid.uuid4().bytes)
    ScannerService().scan_full(db, scan_root=str(tmp_path))
    old, new = sorted(entries_for(db, tmp_path), key=lambda entry: entry.version)
    old.metadata_status = MetadataStatus.MATCHED
    old.metadata_source = "VNDB"
    old.metadata_source_code = "v17"
    db.commit()

    service = CountingMetadataService()
    assert service.auto_match_archive(db, new) is True
    assert (new.metadata_source, new.metadata_source_code) == ("VNDB", "v17")
    assert service.searches == 0
    assert service.refreshed == [new.id]


def test_grouped_search_and_versions_endpoint(db, tmp_path):
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    name = unique_word()
    for version in ("1.0", "1.2", "1.10"):
        (tmp_path / f"{name} v{version}.zip").write_bytes(uuid.uuid4().bytes)
    ScannerService().scan_full(db, scan_root=str(tmp_path))
    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    grouped = client.get("/api/search/", params={"q": name, "group_versions": "true"}, headers=headers).json()
    assert [(entry["version"], entry["version_count"]) for entry in grouped] == [("1.10", 3)]
    assert len(client.get("/api/search/", params={"q": name}, headers=headers).json()) == 3

    versions = client.get(f"/api/archive-entries/{grouped[0]['id']}/versions", headers=headers).json()
    assert [entry["version"] for entry in versions] == ["1.10", "1.2", "1.0"]
