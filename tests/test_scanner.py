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