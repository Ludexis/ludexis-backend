from pathlib import Path
from tests.test_db import TestingSessionLocal
from app.services.scanner import ScannerService
import uuid

def test_scan_empty_folder(tmp_path):
    db = TestingSessionLocal()
    scanner = ScannerService()
    result = scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    assert result["created"] == 0
    db.close()


def test_scan_single_archive(tmp_path):
    db = TestingSessionLocal()
    archive = tmp_path / f"{uuid.uuid4()}.rar"
    archive.write_bytes(uuid.uuid4().hex.encode())
    scanner = ScannerService()
    result = scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    assert result["created"] >= 1
    db.close()


def test_duplicate_scan_does_not_create_duplicates(tmp_path):
    db = TestingSessionLocal()
    archive = tmp_path / f"{uuid.uuid4()}.rar"
    archive.write_bytes(uuid.uuid4().hex.encode())
    scanner = ScannerService()
    first = scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    second = scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    assert first["created"] >= 1
    assert second["created"] == 0
    db.close()


def test_incremental_scan_detects_new_file(tmp_path):
    db = TestingSessionLocal()
    scanner = ScannerService()
    first = tmp_path / f"{uuid.uuid4()}.rar"
    first.write_bytes(uuid.uuid4().hex.encode())
    scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    second = tmp_path / f"{uuid.uuid4()}.rar"
    second.write_bytes(uuid.uuid4().hex.encode())
    result = scanner.scan_incremental(
        db,
        scan_root=str(tmp_path),
    )
    assert result["created"] == 1
    db.close()

def test_scan_library_with_subdirectory(tmp_path):
    db = TestingSessionLocal()
    # Organizing folder: only archives and subfolders, so its archives are scanned.
    category = tmp_path / f"RPG {uuid.uuid4().hex}"
    category.mkdir()
    (category / f"{uuid.uuid4()}.zip").write_bytes(uuid.uuid4().hex.encode())
    (category / "desktop.ini").write_text("")
    # Unpacked game folder: one entry, its subfolders and executables are not entries.
    game_dir = category / f"Game {uuid.uuid4().hex}"
    (game_dir / "bin").mkdir(parents=True)
    (game_dir / "data" / "maps").mkdir(parents=True)
    (game_dir / "readme.txt").write_text("game")
    (game_dir / "bin" / "game.exe").write_bytes(uuid.uuid4().hex.encode())
    (game_dir / "bin" / "engine.dll").write_bytes(b"dll")
    result = ScannerService().scan_full(
        db,
        scan_root=str(tmp_path),
    )
    assert result["created"] == 2
    db.close()


def test_rescan_updates_changed_archive(tmp_path):
    db = TestingSessionLocal()
    archive = tmp_path / f"{uuid.uuid4()}.zip"
    archive.write_bytes(b"first")
    scanner = ScannerService()
    scanner.scan_full(db, scan_root=str(tmp_path))
    archive.write_bytes(b"second, longer content")

    result = scanner.scan_incremental(db, scan_root=str(tmp_path))

    entry = scanner.repo.get_by_file_path(db, str(archive.resolve()))
    assert result["updated"] == 1
    assert entry.file_size == len(b"second, longer content")
    db.close()


def test_moved_archive_keeps_its_entry(tmp_path):
    db = TestingSessionLocal()
    content = uuid.uuid4().hex.encode()
    old_dir, new_dir = tmp_path / "old", tmp_path / "new"
    old_dir.mkdir()
    new_dir.mkdir()
    (old_dir / "Moved_Game.zip").write_bytes(content)
    scanner = ScannerService()
    scanner.scan_full(db, scan_root=str(old_dir))
    (old_dir / "Moved_Game.zip").rename(new_dir / "Moved_Game.zip")

    result = scanner.scan_full(db, scan_root=str(new_dir))

    assert result == {**result, "created": 0, "moved": 1}
    db.close()


def test_copy_of_existing_archive_gets_its_own_entry(tmp_path):
    db = TestingSessionLocal()
    content = uuid.uuid4().hex.encode()
    (tmp_path / "Copy_A.zip").write_bytes(content)
    (tmp_path / "Copy_B.zip").write_bytes(content)

    result = ScannerService().scan_full(db, scan_root=str(tmp_path))

    assert result["created"] == 2
    db.close()


def test_failing_file_does_not_abort_scan(tmp_path, monkeypatch):
    db = TestingSessionLocal()
    for name in ("Good_One.zip", "Broken.zip", "Good_Two.zip"):
        (tmp_path / f"{uuid.uuid4().hex}_{name}").write_bytes(uuid.uuid4().hex.encode())
    scanner = ScannerService()
    original_hash = scanner._compute_file_hash

    def flaky_hash(path):
        if "Broken" in path.name:
            raise OSError("unreadable")
        return original_hash(path)

    monkeypatch.setattr(scanner, "_compute_file_hash", flaky_hash)
    progress = []

    result = scanner.scan_full(db, scan_root=str(tmp_path), on_progress=lambda done, total: progress.append((done, total)))

    assert result["created"] == 2
    assert result["errors"] == 1
    assert progress[-1] == (3, 3)
    db.close()


def test_deleted_entry_stays_deleted_and_keeps_its_file(tmp_path):
    from app.repositories.archive_entry import ArchiveEntryRepository

    db = TestingSessionLocal()
    archive = tmp_path / f"{uuid.uuid4()}.rar"
    archive.write_bytes(uuid.uuid4().hex.encode())
    scanner = ScannerService()
    first = scanner.scan_full(db, scan_root=str(tmp_path))
    repo = ArchiveEntryRepository()
    repo.delete(db, repo.get(db, first["created_ids"][0]))

    again = scanner.scan_full(db, scan_root=str(tmp_path))
    assert archive.exists()
    assert again["created"] == 0
    assert again["ignored_deleted"] == 1
    db.close()
