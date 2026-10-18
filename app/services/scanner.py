from dataclasses import dataclass, fields
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
# Called with (processed, total) as the scan goes on.
ProgressCallback = Callable[[int, int], None]
# Progress is counted in hash-sized chunks, so the bar moves while a large archive is read.
HASH_CHUNK = 1024 * 1024
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
        # Whether an indexed entry's file is still there. A report from an edge device answers this from its listing,
        # since the server cannot see that machine's drives; it also never hashes files itself then.
        self.exists: Callable[[ArchiveEntry], bool] = lambda entry: Path(entry.file_path).exists()
        self.hash_files = True

    def _compute_file_hash(self, path: Path, on_chunk: Callable[[int], None] | None = None) -> str | None:
        # Folder entries have no single file to hash.
        if path.is_dir():
            return None
        sha256 = hashlib.sha256()

        with open(path, "rb") as f:
            chunks = 0
            while chunk := f.read(HASH_CHUNK):
                sha256.update(chunk)
                chunks += 1
                if on_chunk:
                    on_chunk(chunks)

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
    
    def verify_archives(self, db: Session, library_id: str | None = None,) -> dict[str, int]:
        stats = {
            "verified": 0,
            "missing": 0,
            "corrupted": 0,
        }
        archives = self.repo.list_in_library(db, library_id) if library_id else self.repo.list_all(db)
        for archive in archives:
            # An unplugged drive must not turn its entries MISSING; an edge device's drives are not visible here.
            if archive.library is not None and (archive.library.status == LibraryStatus.OFFLINE or archive.library.edge_id):
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

    def scan_full(self, db: Session, scan_root: str | None = None, job_id: str | None = None, on_progress: ProgressCallback | None = None, library_id: str | None = None,) -> dict:
        library_scans_total.inc()
        return self._scan(db, "Full scan", scan_root, job_id, on_progress, incremental=False, library_id=library_id)

    def scan_incremental(self, db: Session, scan_root: str | None = None, job_id: str | None = None, on_progress: ProgressCallback | None = None, library_id: str | None = None,) -> dict:
        incremental_scans_total.inc()
        return self._scan(db, "Incremental scan", scan_root, job_id, on_progress, incremental=True, library_id=library_id)

    def _scan(self, db: Session, label: str, scan_root: str | None, job_id: str | None, on_progress: ProgressCallback | None, incremental: bool, library_id: str | None = None,) -> dict:
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
                # A library picked by hand is scanned even when it is left out of scans of everything.
                if (library.id != library_id) if library_id else not library.enabled:
                    continue
                # Edge device libraries are scanned by their device and arrive through ingest_report.
                if library.edge_id:
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

        stats = self._ingest_batches(db, batches, job_id, on_progress, self.verify_archives)
        stats["offline_libraries"] = offline
        if library_id:
            stats["library"] = next((library.name for library, _, _ in batches), None) or ", ".join(offline)
        if stats["cancelled"]:
            return stats
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

    def _ingest_batches(self, db: Session, batches: list, job_id: str | None, on_progress: ProgressCallback | None, verify: Callable[[Session, str], dict],) -> dict:
        """Stores (library, items, reconnected) batches; verify(db, library_id) checks a library that came back."""
        stats = {
            "created": 0,
            "updated": 0,
            "moved": 0,
            "ignored_deleted": 0,
            "errors": 0,
            "cancelled": False,
            "created_ids": [],
        }
        stats["reconnected_libraries"] = [library.name for library, _, reconnected in batches if reconnected]
        stats["missing"] = 0
        weigh = self._progress_weight if self.hash_files else (lambda item: 1)
        total = sum(weigh(item) for _, items, _ in batches for item in items)
        done = 0
        for library, items, _ in batches:
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
                weight = weigh(item)
                # The last unit is reported once the item is stored, not when its hash is read.
                on_chunk = (lambda chunks, start=done, weight=weight: on_progress(start + min(chunks, weight - 1), total)) if on_progress else None
                self._process_item(db, item, library.id if library is not None else None, stats, on_chunk)
                done += weight
                if on_progress:
                    on_progress(done, total)

        for library, _, _ in batches:
            if library is not None:
                stats["missing"] += self._mark_availability(db, library)
                library.last_scan_at = datetime.now(timezone.utc)
        db.commit()
        # A drive that was away may have come back with changed files, so its entries are checked right away.
        for library, _, reconnected in batches:
            if reconnected:
                for outcome, count in verify(db, library.id).items():
                    stats[f"reconnect_{outcome}"] = stats.get(f"reconnect_{outcome}", 0) + count
        stats.update(GroupingService().regroup(db))
        return stats

    def ingest_report(self, db: Session, library: Library, report: dict, job_id: str | None = None, on_progress: ProgressCallback | None = None,) -> dict:
        """Stores the listing an edge device made of one of its libraries, like a scan of a folder on this server.

        The listing is the whole library, so a path missing from it is gone. Paths outside this library are never
        judged from it, which at worst indexes a second copy and never loses an entry.
        """
        names = {field.name for field in fields(ArchiveScanItem)}
        items = [
            ArchiveScanItem(**{
                **{key: value for key, value in item.items() if key in names},
                "modified_time": datetime.fromisoformat(item["modified_time"]) if item.get("modified_time") else None,
            })
            for item in report.get("items", [])
        ]
        was_offline = library.status == LibraryStatus.OFFLINE
        error = report.get("error")
        if not error and not items and not report.get("pending") and self.repo.count_in_library(db, library.id):
            # Same rule as check_library: an unplugged drive can look like an empty folder.
            error = "Library folder is empty but has indexed entries"
        drive = report.get("drive") or {}
        if drive.get("id"):
            library.drive_id = drive["id"]
            library.drive_subpath = drive.get("subpath")
            library.drive_mount = drive.get("mount")
        library.status = LibraryStatus.OFFLINE.value if error else LibraryStatus.ONLINE.value
        library.last_error = error
        if not error:
            library.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        if error:
            logger.warning("Edge library offline", extra={"library": library.name, "reason": error})
            return {"created": 0, "updated": 0, "moved": 0, "errors": 0, "cancelled": False, "created_ids": [], "offline_libraries": [library.name], "library": library.name}

        # An automatic scan lists new or resized files (relative paths) under "pending" without hashing them: they are
        # left for a scan the user starts, and still count as present so their entries are not marked missing meanwhile.
        pending = set(report.get("pending") or [])
        listed = {item.file_path for item in items}

        def exists(entry: ArchiveEntry) -> bool:
            if entry.library_id == library.id:
                return entry.file_path in listed or entry.relative_path in pending
            other = entry.library
            return Path(entry.file_path).exists() if other is not None and other.edge_id is None else True

        # The device hashes only new or changed files; a file of unchanged size keeps the hash already stored.
        known = {entry.relative_path: entry for entry in self.repo.list_in_library(db, library.id) if entry.relative_path}
        for item in items:
            entry = known.get(item.relative_path)
            if item.file_hash is None and entry is not None and entry.file_size == item.file_size:
                item.file_hash = entry.file_hash

        self.exists = exists
        self.hash_files = False
        # A drive that comes back is not hashed again in full; size changes show up as pending files instead.
        stats = self._ingest_batches(db, [(library, items, was_offline)], job_id, on_progress, lambda db, library_id: {})
        library.pending_changes = len(pending)
        db.commit()
        stats["pending"] = library.pending_changes
        stats["offline_libraries"] = []
        stats["library"] = library.name
        logger.info("Edge report stored", extra={"job_id": job_id, "library": library.name, "archives_created": stats["created"], "archives_moved": stats["moved"]})
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

    def _progress_weight(self, item: ArchiveScanItem) -> int:
        # One unit per item plus one per chunk it may have to hash; folders are never hashed.
        return 1 + (item.file_size or 0) // HASH_CHUNK

    def _relative_path(self, file_path: str, root: Path) -> str | None:
        try:
            return Path(file_path).relative_to(root.resolve()).as_posix()
        except ValueError:
            return None

    def _mark_availability(self, db: Session, library: Library) -> int:
        # Entries whose file is gone become MISSING; ones that came back are verified again later.
        missing = 0
        for entry in self.repo.list_in_library(db, library.id):
            exists = self.exists(entry)
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

    def _process_item(self, db: Session, item: ArchiveScanItem, library_id: str | None, stats: dict, on_chunk: Callable[[int], None] | None = None,) -> None:
        try:
            self._ingest(db, item, library_id, stats, on_chunk)
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

    def _ingest(self, db: Session, item: ArchiveScanItem, library_id: str | None, stats: dict, on_chunk: Callable[[int], None] | None = None,) -> None:
        existing = self.repo.get_by_file_path(db, item.file_path)
        if existing:
            changed = (
                existing.file_size != item.file_size
                or existing.modified_time != item.modified_time
            )
            missing_hash = existing.file_hash is None and item.archive_type != SUPPORTED_FOLDER_TYPE
            if not (changed or missing_hash):
                # A re-added library gets a new id; its entries follow it.
                relink = {"relative_path": item.relative_path, "library_id": library_id}
                relink = {key: value for key, value in relink.items() if value and getattr(existing, key) != value}
                if relink:
                    self.repo.update(db, existing, relink)
                return
            self._ensure_file_hash(item, on_chunk)
            update = {
                "file_size": item.file_size,
                "modified_time": item.modified_time,
                "file_hash": item.file_hash,
                "relative_path": item.relative_path or existing.relative_path,
                "library_id": library_id or existing.library_id,
            }
            if changed:
                update["verification_status"] = VerificationStatus.UNKNOWN
            self.repo.update(db, existing, update)
            stats["updated"] += 1
            return

        # A game the user deleted stays deleted; its files on disk were never touched.
        if self.repo.was_deleted(db, item.file_path, library_id, item.relative_path):
            stats["ignored_deleted"] += 1
            return

        # Same place inside the library under a new root (re-pointed library, new drive letter):
        # the entry moved with its library. Folders have no hash, so this is their only move key.
        if library_id and item.relative_path:
            candidate = self.repo.get_by_relative_path(db, library_id, item.relative_path)
            if candidate is not None and not self.exists(candidate):
                self.repo.update(db, candidate, {
                    "file_path": item.file_path,
                    "file_size": item.file_size,
                    "modified_time": item.modified_time,
                })
                stats["moved"] += 1
                return

        self._ensure_file_hash(item, on_chunk)
        if item.file_hash:
            for candidate in self.repo.get_all_by_hash(db, item.file_hash):
                # Same content at a new path while the old path is gone means the archive was moved;
                # if the old file still exists this is a second copy and gets its own entry.
                if not self.exists(candidate):
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

    def _ensure_file_hash(self, item: ArchiveScanItem, on_chunk: Callable[[int], None] | None = None,) -> None:
        if item.file_hash is None and self.hash_files:
            item.file_hash = self._compute_file_hash(
                Path(item.file_path),
                on_chunk,
            )
    
    def find_duplicates(self, db: Session, viewer=None) -> list[dict]:
        entries = self.repo.list_with_hashes(db, viewer)
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
