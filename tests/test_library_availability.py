import shutil
import uuid

import pytest

from app.models.archive_entry import ArchiveEntry
from app.models.library import Library
from app.services.scanner import ScannerService
from app.utils.enums import VerificationStatus
from tests.test_db import TestingSessionLocal


@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


def make_library(db, path) -> Library:
    library = Library(name=f"lib-{uuid.uuid4().hex[:8]}", path=str(path))
    db.add(library)
    db.commit()
    return library


def populate(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "Alpha Story v1.0.zip").write_bytes(uuid.uuid4().bytes)
    game = root / "Beta Story v2.0"
    game.mkdir()
    (game / "game.exe").write_bytes(uuid.uuid4().bytes)
    (game / "script.rpy").write_text("label start:")


def entries_of(db, library) -> list[ArchiveEntry]:
    db.expire_all()
    return db.query(ArchiveEntry).filter(ArchiveEntry.library_id == library.id).all()


def test_missing_library_goes_offline_and_keeps_entries(db, tmp_path):
    root = tmp_path / "games"
    populate(root)
    library = make_library(db, root)
    ScannerService().scan_full(db)
    assert len(entries_of(db, library)) == 2
    for entry in entries_of(db, library):
        entry.verification_status = VerificationStatus.VERIFIED
    db.commit()

    root.rename(tmp_path / "unplugged")
    stats = ScannerService().scan_incremental(db)
    db.refresh(library)

    assert library.status == "OFFLINE"
    assert library.last_error == "Library folder not found"
    assert library.name in stats["offline_libraries"]
    assert {entry.verification_status for entry in entries_of(db, library)} == {VerificationStatus.VERIFIED}

    # Integrity verification leaves an offline library's entries alone too.
    ScannerService().verify_archives(db)
    assert {entry.verification_status for entry in entries_of(db, library)} == {VerificationStatus.VERIFIED}

    (tmp_path / "unplugged").rename(root)
    stats = ScannerService().scan_incremental(db)
    db.refresh(library)
    assert library.status == "ONLINE"
    assert library.name in stats["reconnected_libraries"]
    assert len(entries_of(db, library)) == 2


def test_empty_root_with_entries_is_offline(db, tmp_path):
    root = tmp_path / "mount"
    populate(root)
    library = make_library(db, root)
    ScannerService().scan_full(db)

    for child in root.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    ScannerService().scan_incremental(db)
    db.refresh(library)

    assert library.status == "OFFLINE"
    assert len(entries_of(db, library)) == 2


def test_deleted_file_in_online_library_becomes_missing(db, tmp_path):
    root = tmp_path / "games"
    populate(root)
    library = make_library(db, root)
    ScannerService().scan_full(db)

    (root / "Alpha Story v1.0.zip").unlink()
    stats = ScannerService().scan_incremental(db)

    assert stats["missing"] == 1
    statuses = {entry.title: entry.verification_status for entry in entries_of(db, library)}
    assert statuses["Alpha Story"] == VerificationStatus.MISSING


def test_new_library_path_relinks_entries(db, tmp_path):
    old_root = tmp_path / "old-drive" / "games"
    populate(old_root)
    library = make_library(db, old_root)
    ScannerService().scan_full(db)
    before = {entry.relative_path: entry.id for entry in entries_of(db, library)}
    assert set(before) == {"Alpha Story v1.0.zip", "Beta Story v2.0"}

    new_root = tmp_path / "new-drive" / "games"
    new_root.parent.mkdir()
    old_root.rename(new_root)
    library.path = str(new_root)
    db.commit()
    stats = ScannerService().scan_incremental(db)

    after = {entry.relative_path: entry for entry in entries_of(db, library)}
    assert {path: entry.id for path, entry in after.items()} == before
    assert all(entry.file_path.startswith(str(new_root.resolve())) for entry in after.values())
    assert stats["created"] == 0
