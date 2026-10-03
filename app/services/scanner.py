from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from datetime import datetime, UTC, timezone
import hashlib
import time

from app.core.config import settings
from app.models.archive_entry import ArchiveEntry
from app.repositories.archive_entry import ArchiveEntryRepository
from app.utils.enums import LibraryStatus, MetadataStatus, VerificationStatus
from app.models.library import Library
from app.utils.normalization import parse_archive_name
from sqlalchemy.orm import Session
from app.models.job_history import JobHistory
from app.utils.enums import JobStatus
from app.repositories.library import LibraryRepository
from app.services.grouping import GroupingService

from app.core.logging import get_logger
from app.core.metrics import library_scans_total, incremental_scans_total

logger = get_logger(__name__)

SUPPORTED_ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".iso", ".exe"}
SUPPORTED_FOLDER_TYPE = "folder"
# Called with (processed, total) after each discovered item.
ProgressCallback = Callable[[int, int], None]
# OS-generated files that do not make an organizing folder a game folder.
IGNORED_FILE_NAMES = {"desktop.ini", "thumbs.db"}


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
    relative_path: str | None = None


class ScannerService:
    def __init__(self) -> None:
        self.repo = ArchiveEntryRepository()
        self.library_repo = LibraryRepository()

    def _compute_file_hash(self, path: Path) -> str | None:
        # Folder entries have no single file to hash.
        if path.is_dir():
            return None
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
    
    def _job_cancelled(self, db: Session, job_id: str | None,) -> bool:
        if not job_id:
            return False

        status = (db.query(JobHistory.status).filter(JobHistory.id == job_id).scalar())
        return (status== JobStatus.CANCELED)

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
            # An unplugged drive must not turn its entries MISSING.
            if archive.library is not None and archive.library.status == LibraryStatus.OFFLINE:
                continue
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

    def scan_full(self, db: Session, scan_root: str | None = None, job_id: str | None = None, on_progress: ProgressCallback | None = None,) -> dict:
        library_scans_total.inc()
        return self._scan(db, "Full scan", scan_root, job_id, on_progress, incremental=False)

    def scan_incremental(self, db: Session, scan_root: str | None = None, job_id: str | None = None, on_progress: ProgressCallback | None = None,) -> dict:
        incremental_scans_total.inc()
        return self._scan(db, "Incremental scan", scan_root, job_id, on_progress, incremental=True)

    def _scan(self, db: Session, label: str, scan_root: str | None, job_id: str | None, on_progress: ProgressCallback | None, incremental: bool,) -> dict:
        logger.info(
            f"{label} started",
            extra={
                "job_id": job_id,
                "scan_root": scan_root,
            },
        )
        offline: list[str] = []
        if scan_root:
            targets = [(None, Path(scan_root), False)]
        else:
            targets = []
            for library in self.library_repo.list_active(db):
                if not library.enabled:
                    continue
                was_offline = library.status == LibraryStatus.OFFLINE
                if self.check_library(db, library):
                    targets.append((library, Path(library.path), was_offline))
                else:
                    offline.append(library.name)

        # Discover everything up front so progress is reported against a known total.
        batches = []
        for library, root, reconnected in targets:
            items = self._discover_items(root)
            if library is not None:
                for item in items:
                    item.relative_path = self._relative_path(item.file_path, root)
            batches.append((library, items, reconnected))
        if incremental:
            existing_entries = {entry.file_path: entry for entry in self.repo.list_all(db)}
            # A library that just came back online is scanned in full.
            batches = [
                (library, items if reconnected else [item for item in items if self._needs_processing(item, existing_entries)], reconnected)
                for library, items, reconnected in batches
            ]

        stats = {
            "created": 0,
            "updated": 0,
            "moved": 0,
            "errors": 0,
            "cancelled": False,
            "created_ids": [],
        }
        stats["offline_libraries"] = offline
        stats["reconnected_libraries"] = [library.name for library, _, reconnected in batches if reconnected]
        stats["missing"] = 0
        total = sum(len(items) for _, items, _ in batches)
        done = 0
        for library, items, _ in batches:
            library_id = library.id if library is not None else None
            for item in items:
                if self._job_cancelled(db, job_id):
                    stats["cancelled"] = True
                    logger.warning(
                        "Scan cancelled",
                        extra={
                            "job_id": job_id,
                        },
                    )
                    return stats
                self._process_item(db, item, library_id, stats)
                done += 1
                if on_progress:
                    on_progress(done, total)

        for library, _, _ in batches:
            if library is not None:
                stats["missing"] += self._mark_availability(db, library)
                library.last_scan_at = datetime.now(timezone.utc)
        db.commit()
        stats.update(GroupingService().regroup(db))
        logger.info(
            f"{label} completed",
            extra={
                "job_id": job_id,
                "archives_created": stats["created"],
                "archives_updated": stats["updated"],
                "archives_moved": stats["moved"],
                "archives_failed": stats["errors"],
            },
        )
        return stats

    def check_library(self, db: Session, library: Library) -> bool:
        """Record whether the library folder is reachable; offline libraries are skipped, not emptied."""
        root = Path(library.path)
        error = None
        try:
            if not root.is_dir():
                error = "Library folder not found"
            elif not any(root.iterdir()) and self.repo.count_in_library(db, library.id):
                # An unplugged drive behind a bind mount shows up as an empty folder.
                error = "Library folder is empty but has indexed entries"
        except OSError as exc:
            error = f"Library folder not readable: {exc}"
        library.status = LibraryStatus.OFFLINE.value if error else LibraryStatus.ONLINE.value
        library.last_error = error
        if not error:
            library.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        if error:
            logger.warning("Library offline", extra={"library": library.name, "path": library.path, "reason": error})
        return error is None

    def _relative_path(self, file_path: str, root: Path) -> str | None:
        try:
            return Path(file_path).relative_to(root.resolve()).as_posix()
        except ValueError:
            return None

    def _mark_availability(self, db: Session, library: Library) -> int:
        # Entries whose file is gone become MISSING; ones that came back are verified again later.
        missing = 0
        for entry in self.repo.list_in_library(db, library.id):
            exists = Path(entry.file_path).exists()
            if not exists and entry.verification_status != VerificationStatus.MISSING:
                entry.verification_status = VerificationStatus.MISSING
                missing += 1
            elif exists and entry.verification_status == VerificationStatus.MISSING:
                entry.verification_status = VerificationStatus.UNKNOWN
        return missing

    def _discover_items(self, base_path: Path) -> list[ArchiveScanItem]:
        if not base_path.exists():
            return []

        items: list[ArchiveScanItem] = []
        try:
            children = sorted(base_path.iterdir())
        except OSError:
            logger.warning("Directory not readable", extra={"path": str(base_path)})
            return items
        for path in children:
            if path.is_file() and path.suffix.lower() in SUPPORTED_ARCHIVE_EXTENSIONS:
                items.append(self._scan_file(path))
            elif path.is_dir():
                try:
                    is_game_folder = self._is_game_folder(path)
                except OSError:
                    logger.warning("Directory not readable", extra={"path": str(path)})
                    continue
                if is_game_folder:
                    # The whole folder is one game; its subfolders are part of it.
                    items.append(self._scan_folder(path))
                else:
                    items.extend(self._discover_items(path))
        return items

    def _is_game_folder(self, path: Path) -> bool:
        # A folder holding only archives and subfolders organizes the library; any other file means an unpacked game.
        return any(
            child.is_file()
            and child.suffix.lower() not in SUPPORTED_ARCHIVE_EXTENSIONS
            and not child.name.startswith(".")
            and child.name.lower() not in IGNORED_FILE_NAMES
            for child in path.iterdir()
        )

    def _scan_file(self, path: Path) -> ArchiveScanItem:
        stat = path.stat()
        file_hash = None
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

    def _process_item(self, db: Session, item: ArchiveScanItem, library_id: str | None, stats: dict,) -> None:
        try:
            self._ingest(db, item, library_id, stats)
        except Exception:
            # One unreadable or vanished file must not abort the whole scan.
            db.rollback()
            stats["errors"] += 1
            logger.exception(
                "Scan item failed",
                extra={
                    "file_path": item.file_path,
                },
            )

    def _ingest(self, db: Session, item: ArchiveScanItem, library_id: str | None, stats: dict,) -> None:
        existing = self.repo.get_by_file_path(db, item.file_path)
        if existing:
            changed = (
                existing.file_size != item.file_size
                or existing.modified_time != item.modified_time
            )
            missing_hash = existing.file_hash is None and item.archive_type != SUPPORTED_FOLDER_TYPE
            if not (changed or missing_hash):
                if item.relative_path and existing.relative_path != item.relative_path:
                    self.repo.update(db, existing, {"relative_path": item.relative_path})
                return
            self._ensure_file_hash(item)
            update = {
                "file_size": item.file_size,
                "modified_time": item.modified_time,
                "file_hash": item.file_hash,
                "relative_path": item.relative_path or existing.relative_path,
            }
            if changed:
                update["verification_status"] = VerificationStatus.UNKNOWN
            self.repo.update(db, existing, update)
            stats["updated"] += 1
            return

        # Same place inside the library under a new root (re-pointed library, new drive letter):
        # the entry moved with its library. Folders have no hash, so this is their only move key.
        if library_id and item.relative_path:
            candidate = self.repo.get_by_relative_path(db, library_id, item.relative_path)
            if candidate is not None and not Path(candidate.file_path).exists():
                self.repo.update(db, candidate, {
                    "file_path": item.file_path,
                    "file_size": item.file_size,
                    "modified_time": item.modified_time,
                })
                stats["moved"] += 1
                return

        self._ensure_file_hash(item)
        if item.file_hash:
            for candidate in self.repo.get_all_by_hash(db, item.file_hash):
                # Same content at a new path while the old path is gone means the archive was moved;
                # if the old file still exists this is a second copy and gets its own entry.
                if not Path(candidate.file_path).exists():
                    self.repo.update(
                        db,
                        candidate,
                        {
                            "file_path": item.file_path,
                            "file_size": item.file_size,
                            "modified_time": item.modified_time,
                            "library_id": library_id or candidate.library_id,
                            "relative_path": item.relative_path,
                        },
                    )
                    stats["moved"] += 1
                    return

        archive_entry = self.repo.create(db, {
            "title": item.title,
            "version": item.version,
            "archive_type": item.archive_type,
            "file_path": item.file_path,
            "metadata_status": MetadataStatus.UNMATCHED,
            "verification_status": VerificationStatus.UNKNOWN,
            "library_id": library_id,
            "relative_path": item.relative_path,
            "file_size": item.file_size,
            "modified_time": item.modified_time,
            "file_hash": item.file_hash,
        })
        stats["created"] += 1
        stats["created_ids"].append(archive_entry.id)

    def _ensure_file_hash(self, item: ArchiveScanItem,) -> None:
        if item.file_hash is None:
            item.file_hash = self._compute_file_hash(
                Path(item.file_path)
            )
    
    def find_duplicates(self, db: Session,) -> list[dict]:
        entries = self.repo.list_with_hashes(db)
        grouped: dict[str, list] = {}
        for entry in entries:
            grouped.setdefault(
                entry.file_hash,
                [],
            ).append(entry)
        duplicates = []

        for file_hash, matches in grouped.items():
            if len(matches) > 1:
                duplicates.append(
                    {
                        "file_hash": file_hash,
                        "count": len(matches),
                        "entries": matches,
                    }
                )
        return duplicates
