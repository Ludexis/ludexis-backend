from pathlib import Path
from app.db.session import SessionLocal
from app.services.scanner import ScannerService


def test_scan_empty_folder(tmp_path):
    db = SessionLocal()
    scanner = ScannerService()
    result = scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    assert result["created"] == 0
    db.close()


def test_scan_single_archive(tmp_path):
    db = SessionLocal()
    archive = tmp_path / "Pytest_Unique_Game_001.rar"
    archive.write_bytes(b"pytest_unique_game_001")
    scanner = ScannerService()
    result = scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    assert result["created"] >= 1
    db.close()


def test_duplicate_scan_does_not_create_duplicates(tmp_path):
    db = SessionLocal()
    archive = tmp_path / "Pytest_Unique_Game_002.rar"
    archive.write_bytes(b"pytest_unique_game_002")
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
    db = SessionLocal()
    scanner = ScannerService()
    first = tmp_path / "Pytest_Unique_Game_003.rar"
    first.write_bytes(b"pytest_unique_game_003")
    scanner.scan_full(
        db,
        scan_root=str(tmp_path),
    )
    second = tmp_path / "Pytest_Unique_Game_004.rar"
    second.write_bytes(b"pytest_unique_game_004")
    result = scanner.scan_incremental(
        db,
        scan_root=str(tmp_path),
    )
    assert result["created"] == 1
    db.close()