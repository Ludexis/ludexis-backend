import gzip
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app import __version__
from app.core.config import settings
from app.core.edge_auth import hash_edge_token, new_edge_token
from app.core.logging import get_logger
from app.edge.drives import drive_key
from app.models.edge_device import POLL_SECONDS, EdgeDevice
from app.models.archive_entry import ArchiveEntry
from app.models.job_history import JobHistory
from app.models.library import Library
from app.repositories.archive_entry import ArchiveEntryRepository
from app.services.artwork import ArtworkService
from app.services.grouping import GroupingService
from app.services.job import JobService
from app.services.metadata import MATCHED_THRESHOLD, PARTIAL_THRESHOLD, MetadataService
from app.services.scanner import ScannerService
from app.services.settings import SettingsService
from app.utils.enums import JobStatus, JobType, LibraryStatus, MetadataStatus

logger = get_logger(__name__)

# Next to the config folder, so on the data volume the backend and worker share.
REPORTS_DIR = Path(settings.CONFIG_DIR).parent / "edge-reports"
BUNDLE_DIR = Path(__file__).resolve().parent.parent / "edge" / "bundle"
ACTIVE = (JobStatus.PENDING, JobStatus.RUNNING)
# Entries handed to a device per check-in for metadata lookups.
METADATA_BATCH = 20


def _same_release(left: str | None, right: str) -> bool:
    return bool(left) and left.split(".")[:2] == right.split(".")[:2]


class EdgeService:
    def libraries(self, db: Session, edge: EdgeDevice) -> list[Library]:
        return db.query(Library).filter(Library.edge_id == edge.id, Library.deleted_at.is_(None)).order_by(Library.name).all()

    def read(self, db: Session, edge: EdgeDevice) -> dict:
        return {
            "id": edge.id,
            "name": edge.name,
            "status": edge.status,
            "autoscan": edge.autoscan,
            "match_metadata": edge.match_metadata,
            "last_seen_at": edge.last_seen_at,
            "version": edge.version,
            "update_available": edge.version is not None and not _same_release(edge.version, __version__),
            "hostname": edge.hostname,
            "os": edge.os,
            "drives": edge.drives or [],
            "libraries": self.libraries(db, edge),
            "created_at": edge.created_at,
        }

    def list_devices(self, db: Session) -> list[EdgeDevice]:
        return db.query(EdgeDevice).order_by(EdgeDevice.name).all()

    def create(self, db: Session, name: str) -> tuple[EdgeDevice, str]:
        self._ensure_unique(db, name)
        token = new_edge_token()
        edge = EdgeDevice(name=name.strip(), token_hash=hash_edge_token(token))
        db.add(edge)
        db.commit()
        db.refresh(edge)
        return edge, token

    def update(self, db: Session, edge: EdgeDevice, changes: dict) -> EdgeDevice:
        if changes.get("name") is not None:
            self._ensure_unique(db, changes["name"], edge.id)
            changes["name"] = changes["name"].strip()
        for key, value in changes.items():
            if value is not None:
                setattr(edge, key, value)
        db.commit()
        db.refresh(edge)
        return edge

    def rotate_token(self, db: Session, edge: EdgeDevice) -> str:
        token = new_edge_token()
        edge.token_hash = hash_edge_token(token)
        db.commit()
        return token

    def delete(self, db: Session, edge: EdgeDevice) -> None:
        # Its libraries stay with all their entries and fall back to the server, where they show as offline.
        now = datetime.now(UTC)
        for job in db.query(JobHistory).filter(JobHistory.edge_id == edge.id, JobHistory.status.in_(ACTIVE), JobHistory.task_id.is_(None)):
            job.status = JobStatus.CANCELED
            job.details = job.result = f"Edge device {edge.name} was removed"
            job.completed_at = now
        db.delete(edge)
        db.commit()

    def token_matches(self, edge: EdgeDevice, token: str) -> bool:
        return hash_edge_token(token) == edge.token_hash

    def bundle(self, edge: EdgeDevice, os_name: str, token: str, server_url: str) -> bytes:
        """A zip with the compose file, the .env holding the token, and the installer for that system."""
        env = (BUNDLE_DIR / "env.template").read_text(encoding="utf-8").format(
            name=edge.name, server_url=server_url.rstrip("/"), token=token, version=__version__
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("ludexis-edge/.env", env)
            for path in sorted((BUNDLE_DIR / os_name).rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(f"ludexis-edge/{path.relative_to(BUNDLE_DIR / os_name).as_posix()}")
                    # Scripts keep their execute bit when unzipped on Linux.
                    info.external_attr = (0o755 if path.suffix in {".sh", ""} else 0o644) << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, path.read_bytes())
        return buffer.getvalue()

    def poll(self, db: Session, edge: EdgeDevice, data) -> dict:
        previous = {drive_key(drive["id"]) for drive in edge.drives or []}
        current = {drive_key(drive.id) for drive in data.drives}
        edge.last_seen_at = datetime.now(UTC)
        edge.version = data.version
        edge.hostname = data.hostname
        edge.os = data.os
        edge.drives = [drive.model_dump() for drive in data.drives]
        db.commit()
        libraries = self.libraries(db, edge)
        if edge.autoscan:
            connected = current - previous
            for library in libraries:
                key = drive_key(library.drive_id) if library.drive_id else None
                # Its own drive came back, or any drive appeared while an offline library's drive is not known yet.
                if library.enabled and connected and (key in connected or (library.status == LibraryStatus.OFFLINE and key is None)):
                    JobService().queue_edge_scan(db, None, JobType.INCREMENTAL_SCAN, library, f"Drive of {library.name} connected to {edge.name}")
        mine = {library.id for library in libraries}
        jobs = []
        for job in db.query(JobHistory).filter(JobHistory.edge_id == edge.id, JobHistory.status.in_(ACTIVE), JobHistory.task_id.is_(None)).order_by(JobHistory.started_at):
            if job.library_id in mine:
                jobs.append(job)
            else:
                # The library was moved to another machine or deleted after the scan was asked for.
                self._end(job, JobStatus.CANCELED, "The library no longer belongs to this edge device")
        db.commit()
        return {
            "metadata": self._metadata_requests(db, edge) if edge.match_metadata else [],
            "poll_seconds": POLL_SECONDS,
            "server_version": __version__,
            "autoscan": edge.autoscan,
            "match_metadata": edge.match_metadata,
            "provider_order": SettingsService().match_providers(db),
            "libraries": libraries,
            "jobs": jobs,
        }

    def library(self, db: Session, edge: EdgeDevice, library_id: str) -> Library | None:
        return db.query(Library).filter(Library.id == library_id, Library.edge_id == edge.id, Library.deleted_at.is_(None)).one_or_none()

    def library_state(self, db: Session, library: Library) -> dict:
        entries = {
            entry.relative_path: [entry.file_size, entry.modified_time.isoformat() if entry.modified_time else None, entry.file_hash is not None]
            for entry in ArchiveEntryRepository().list_in_library(db, library.id)
            if entry.relative_path
        }
        return {"entries": entries, "verify": library.status == LibraryStatus.OFFLINE}

    def job(self, db: Session, edge: EdgeDevice, job_id: str) -> JobHistory | None:
        return db.query(JobHistory).filter(JobHistory.id == job_id, JobHistory.edge_id == edge.id).one_or_none()

    def progress(self, db: Session, job: JobHistory, done: int, total: int, details: str | None) -> bool:
        """Records progress; returns True when the job was cancelled and the device should stop."""
        if job.status == JobStatus.CANCELED:
            return True
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.RUNNING
        job.progress = min(99, int(done * 100 / total)) if total else 0
        if details:
            job.details = details
        db.commit()
        return False

    def fail(self, db: Session, job: JobHistory, error: str) -> None:
        if job.status in ACTIVE:
            self._end(job, JobStatus.FAILED, error)
            if job.library is not None:
                job.library.last_error = error
            db.commit()

    def save_report(self, db: Session, job: JobHistory, body: bytes) -> JobHistory:
        """Keeps the device's listing and hands it to the server's worker, which stores it under the same job."""
        from app.tasks.scan_tasks import ingest_edge_report_task

        report = json.loads(gzip.decompress(body))
        if report.get("library_id") != job.library_id:
            raise ValueError("The report is for another library")
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / f"{job.id}.json.gz").write_bytes(body)
        job.details = f"Storing {len(report.get('items', []))} items from the edge device"
        db.commit()
        task = ingest_edge_report_task.apply_async(args=[job.id])
        job.task_id = task.id
        db.commit()
        return job

    def ingest(self, db: Session, job_id: str, on_progress=None) -> dict:
        path = REPORTS_DIR / f"{job_id}.json.gz"
        job = db.get(JobHistory, job_id)
        library = job.library if job is not None else None
        if library is None:
            raise ValueError("The library of this edge scan no longer exists")
        report = json.loads(gzip.decompress(path.read_bytes()))
        stats = ScannerService().ingest_report(db, library, report, job_id=job_id, on_progress=on_progress)
        path.unlink(missing_ok=True)
        return stats

    def _metadata_requests(self, db: Session, edge: EdgeDevice) -> list[dict]:
        entries = (
            db.query(ArchiveEntry)
            .join(Library, ArchiveEntry.library_id == Library.id)
            .filter(
                Library.edge_id == edge.id,
                ArchiveEntry.deleted_at.is_(None),
                ArchiveEntry.metadata_override.is_(False),
                ArchiveEntry.metadata_source_code.is_(None),
                ArchiveEntry.last_metadata_refresh.is_(None),
            )
            .order_by(ArchiveEntry.created_at)
            .limit(METADATA_BATCH)
            .all()
        )
        return [{"entry_id": entry.id, "title": entry.title} for entry in entries]

    def apply_metadata(self, db: Session, edge: EdgeDevice, result) -> ArchiveEntry | None:
        """Stores a match the device looked up, with the thresholds and steps of the server's own matching."""
        entry = (
            db.query(ArchiveEntry)
            .join(Library, ArchiveEntry.library_id == Library.id)
            .filter(ArchiveEntry.id == result.entry_id, Library.edge_id == edge.id, ArchiveEntry.deleted_at.is_(None))
            .one_or_none()
        )
        if entry is None or entry.metadata_override:
            return entry
        entry.last_metadata_refresh = datetime.now(UTC)
        entry.metadata_confidence = round(result.score, 3)
        if result.details is None or result.score < PARTIAL_THRESHOLD:
            entry.metadata_status = MetadataStatus.UNMATCHED
            db.commit()
            return entry
        entry.metadata_status = MetadataStatus.MATCHED if result.score >= MATCHED_THRESHOLD else MetadataStatus.PARTIAL
        entry.metadata_source = result.details.provider
        entry.metadata_source_code = result.details.provider_id
        db.commit()
        metadata = MetadataService()
        metadata.refresh_archive(db, entry, result.details)
        ArtworkService(metadata).fill_missing_artwork(db, entry, details=result.details)
        GroupingService().regroup(db)
        return entry

    def _end(self, job: JobHistory, status: JobStatus, reason: str) -> None:
        job.status = status
        job.details = job.result = reason
        job.completed_at = datetime.now(UTC)

    def _ensure_unique(self, db: Session, name: str, current_id: str | None = None) -> None:
        existing = db.query(EdgeDevice).filter(EdgeDevice.name == name.strip()).one_or_none()
        if existing is not None and existing.id != current_id:
            raise ValueError("An edge device with this name already exists")
