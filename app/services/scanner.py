from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from datetime import datetime, timezone
import hashlib

from app.core.config import settings
from app.models.archive_entry import ArchiveEntry
from app.repositories.archive_entry import ArchiveEntryRepository
from app.services.matching import MatchingService
from app.utils.enums import MetadataStatus, VerificationStatus
from app.utils.normalization import parse_archive_name
from sqlalchemy.orm import Session

from app.repositories.library import LibraryRepository

SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".iso", ".exe"}
SUPPORTED_FOLDER_TYPE = "folder"


@dataclass
class ArchiveScanItem:
    file_path: str
    filename: str
    archive_name: str | None
    folder_name: str | None
    title: str
    version: str | None
    archive_type: str
    release_group: str | None = None
    file_size: int | None = None
    modified_time: datetime | None = None
    file_hash: str | None = None


class ScannerService:
    def __init__(self) -> None:
        self.repo = ArchiveEntryRepository()
        self.library_repo = LibraryRepository()
        self.matcher = MatchingService()

    def _compute_file_hash(self, path: Path) -> str:
        sha256 = hashlib.sha256()

        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)

        return sha256.hexdigest()
    
    def _verify_archive(self, db: Session, archive: ArchiveEntry, ) -> VerificationStatus:
        path = Path(archive.file_path)
        if not path.exists():
            return VerificationStatus.MISSING
        current_hash = self._compute_file_hash(path)
        if archive.file_hash != current_hash:
            return VerificationStatus.CORRUPTED
        return VerificationStatus.VERIFIED

    def _needs_processing(self, item: ArchiveScanItem, existing_entries: dict, ) -> bool:
        existing = existing_entries.get(item.file_path)
        if existing is None:
            return True
        if (
            existing.file_size != item.file_size
            or
            existing.modified_time != item.modified_time
        ):
            return True
        return False
    
    def verify_archives(self, db: Session, ) -> dict[str, int]:
        stats = {
            "verified": 0,
            "missing": 0,
            "corrupted": 0,
        }
        archives = self.repo.list_all(db)
        for archive in archives:
            status = self._verify_archive(
                db,
                archive,
            )
            self.repo.update(
                db,
                archive,
                {
                    "verification_status": status,
                    "last_verified": datetime.now(
                        timezone.utc,
                    ),
                },
            )
            if status == VerificationStatus.VERIFIED:
                stats["verified"] += 1
            elif status == VerificationStatus.MISSING:
                stats["missing"] += 1
            elif status == VerificationStatus.CORRUPTED:
                stats["corrupted"] += 1
        return stats

    def scan_full(self, db: Session, scan_root: str | None = None, ) -> dict[str, int]:
        if scan_root:
            return self._process_items(
                db,
                self._discover_items(Path(scan_root)),
            )
        libraries = self.library_repo.list_active(db)
        stats = {
            "created": 0,
            "matched": 0,
            "partial": 0,
            "unmatched": 0,
        }
        for library in libraries:
            if not library.enabled:
                continue
            library_stats = self._process_items(
                db,
                self._discover_items(Path(library.path)),
                library_id=library.id,
            )
            for key in stats:
                stats[key] += library_stats[key]
        return stats

    def scan_incremental(self, db: Session, scan_root: str | None = None,) -> dict[str, int]:
        existing_entries = {
            entry.file_path: entry
            for entry in self.repo.list_all(db)
        }
        if scan_root:
            items = [
                item
                for item in self._discover_items(Path(scan_root))
                if self._needs_processing(
                    item,
                    existing_entries,
                )
            ]
            return self._process_items(
                db,
                items,
            )
        libraries = self.library_repo.list_active(db)
        stats = {
            "created": 0,
            "matched": 0,
            "partial": 0,
            "unmatched": 0,
        }
        for library in libraries:
            if not library.enabled:
                continue
            items = [
                item
                for item in self._discover_items(
                    Path(library.path)
                )
                if self._needs_processing(
                    item,
                    existing_entries,
                )
            ]
            library_stats = self._process_items(
                db,
                items,
                library_id=library.id,
            )
            for key in stats:
                stats[key] += library_stats[key]
        return stats

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
        stat = path.stat()
        file_hash = self._compute_file_hash(path)
        parsed = parse_archive_name(path.name)
        file_size = stat.st_size
        modified_time = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc,)

        return ArchiveScanItem(
            file_path=str(path.resolve()),
            filename=path.name,
            archive_name=path.stem,
            folder_name=path.parent.name if path.parent != path else None,
            title=parsed.title,
            version=parsed.version,
            archive_type=parsed.archive_type or path.suffix.lstrip(".").upper(),
            release_group=parsed.release_group,
            file_size=file_size,
            modified_time=modified_time,
            file_hash=file_hash,
        )

    def _scan_folder(self, path: Path) -> ArchiveScanItem:
        parsed = parse_archive_name(path.name)

        return ArchiveScanItem(
            file_path=str(path.resolve()),
            filename=path.name,
            archive_name=None,
            folder_name=path.name,

            title=parsed.title,
            version=parsed.version,

            archive_type=SUPPORTED_FOLDER_TYPE,

            release_group=parsed.release_group,
            file_size=None,
            modified_time=None,
        )

    def _process_items(self, db: Session, items: Iterable[ArchiveScanItem], library_id: str | None = None,) -> dict[str, int]:
        stats = {"created": 0, "matched": 0, "partial": 0, "unmatched": 0}
        for item in items:
            existing_by_path = self.repo.get_by_file_path(
                db,
                item.file_path,
            )

            if existing_by_path:
                if (
                    existing_by_path.file_size is None
                    or
                    existing_by_path.modified_time is None
                    or
                    existing_by_path.file_hash is None
                ):
                    self.repo.update(
                        db,
                        existing_by_path,
                        {
                            "file_size": item.file_size,
                            "modified_time": item.modified_time,
                            "file_hash": item.file_hash,
                        },
                    )

                continue

            existing_by_hash = None
            if item.file_hash:
                existing_by_hash = self.repo.get_by_hash(
                    db,
                    item.file_hash,
                )
            if existing_by_hash:
                self.repo.update(
                    db,
                    existing_by_hash,
                    {
                        "file_path": item.file_path,
                        "file_size": item.file_size,
                        "modified_time": item.modified_time,
                    },
                )
                continue

            existing = self.repo.get_by_title_and_version(
            db,
            item.title,
            item.version,
            )

            if existing:
                stats["matched"] += 1
                continue

            match_type, confidence = self.matcher.match_title(db, item.title, item.version,)
            metadata_status = self.matcher.metadata_status_for_match(match_type)
            archive_entry = self.repo.create(db, {
                "title": item.title,
                "description": None,
                "version": item.version,
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
                "library_id": library_id,
                "file_size": item.file_size,
                "modified_time": item.modified_time,
                "file_hash": item.file_hash,
            })
            stats["created"] += 1
            if metadata_status == MetadataStatus.MATCHED:
                stats["matched"] += 1
            elif metadata_status == MetadataStatus.PARTIAL:
                stats["partial"] += 1
            else:
                stats["unmatched"] += 1

        return stats
