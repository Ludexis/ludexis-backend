from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.core.config import settings
from app.models.archive_entry import ArchiveEntry
from app.repositories.archive_entry import ArchiveEntryRepository
from app.services.matching import MatchingService
from app.utils.enums import MetadataStatus, VerificationStatus
from app.utils.normalization import normalize_archive_name
from sqlalchemy.orm import Session


SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".iso", ".exe"}
SUPPORTED_FOLDER_TYPE = "folder"


@dataclass
class ArchiveScanItem:
    file_path: str
    filename: str
    archive_name: str | None
    folder_name: str | None
    archive_type: str
    normalized_title: str


class ScannerService:
    def __init__(self) -> None:
        self.repo = ArchiveEntryRepository()
        self.matcher = MatchingService()

    def scan_full(self, db: Session, scan_root: str | None = None) -> dict[str, int]:
        base_path = Path(scan_root or settings.LIBRARY_SCAN_PATH)
        items = self._discover_items(base_path)
        return self._process_items(db, items)

    def scan_incremental(self, db: Session, scan_root: str | None = None) -> dict[str, int]:
        base_path = Path(scan_root or settings.LIBRARY_SCAN_PATH)
        existing_paths = {entry.file_path for entry in self.repo.list_all(db)}
        items = [item for item in self._discover_items(base_path) if item.file_path not in existing_paths]
        return self._process_items(db, items)

    def _discover_items(self, base_path: Path) -> list[ArchiveScanItem]:
        if not base_path.exists():
            return []

        items: list[ArchiveScanItem] = []
        for path in base_path.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_ARCHIVE_EXTENSIONS:
                items.append(self._scan_file(path))
            elif path.is_dir():
                items.append(self._scan_folder(path))
        return items

    def _scan_file(self, path: Path) -> ArchiveScanItem:
        return ArchiveScanItem(
            file_path=str(path.resolve()),
            filename=path.name,
            archive_name=path.stem,
            folder_name=path.parent.name if path.parent != path else None,
            archive_type=path.suffix.lstrip(".").upper(),
            normalized_title=normalize_archive_name(path.stem),
        )

    def _scan_folder(self, path: Path) -> ArchiveScanItem:
        return ArchiveScanItem(
            file_path=str(path.resolve()),
            filename=path.name,
            archive_name=None,
            folder_name=path.name,
            archive_type=SUPPORTED_FOLDER_TYPE,
            normalized_title=normalize_archive_name(path.name),
        )

    def _process_items(self, db: Session, items: Iterable[ArchiveScanItem]) -> dict[str, int]:
        stats = {"created": 0, "matched": 0, "partial": 0, "unmatched": 0}
        for item in items:
            if self.repo.get_by_file_path(db, item.file_path):
                continue

            match_type, confidence = self.matcher.match_title(db, item.normalized_title)
            metadata_status = self.matcher.metadata_status_for_match(match_type)
            archive_entry = self.repo.create(db, {
                "title": item.normalized_title,
                "description": None,
                "version": None,
                "engine": None,
                "release_date": None,
                "archive_type": item.archive_type,
                "file_path": item.file_path,
                "storage_device": None,
                "cover_path": None,
                "banner_path": None,
                "logo_path": None,
                "metadata_status": metadata_status,
                "metadata_source": None,
                "metadata_source_code": None,
                "last_metadata_refresh": None,
                "last_verified": None,
                "verification_status": VerificationStatus.UNKNOWN,
                "parent_series_id": None,
                "franchise_id": None,
            })
            stats["created"] += 1
            if metadata_status == MetadataStatus.MATCHED:
                stats["matched"] += 1
            elif metadata_status == MetadataStatus.PARTIAL:
                stats["partial"] += 1
            else:
                stats["unmatched"] += 1

        return stats
