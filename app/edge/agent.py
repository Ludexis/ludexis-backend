"""Ludexis edge device: scans the drives attached to this machine and sends the listings to the server.

It keeps no database: every check-in tells it which libraries are its own and which scans are waiting, and the
server stores what it finds. It needs only LUDEXIS_SERVER_URL and LUDEXIS_EDGE_TOKEN.
"""

import dataclasses
import gzip
import json
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

from app import __version__
from app.core.logging import get_logger, setup_logging
from app.edge.drives import STATE_DIR, EdgePathError, library_root, visible_drives
from app.providers.igdb import IGDBProvider
from app.providers.plugins import load_plugin_providers
from app.providers.steam import SteamProvider
from app.providers.vndb import VNDBProvider
from app.services.metadata import PARTIAL_THRESHOLD, MetadataService
from app.services.scanner import SUPPORTED_FOLDER_TYPE, ScannerService

logger = get_logger("app.edge")

ALIVE_FILE = Path("/tmp/ludexis-edge-alive")
PROGRESS_EVERY = 2.0
# Waits between failed check-ins, so a server that is down is not hammered.
BACKOFF = (5, 15, 30, 60)


class Cancelled(Exception):
    pass


class EdgeAgent:
    def __init__(self, server_url: str, token: str, os_name: str) -> None:
        self.server = server_url.rstrip("/") + "/api/edge/agent"
        self.os_name = os_name
        self.http = requests.Session()
        self.http.headers.update({"Authorization": f"Bearer {token}", "User-Agent": f"ludexis-edge/{__version__}"})
        self.scanner = ScannerService()
        self.running: str | None = None
        self.drives = []

    def _call(self, method: str, path: str, **kwargs):
        response = self.http.request(method, self.server + path, timeout=kwargs.pop("timeout", 30), **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    def poll(self) -> dict:
        self.drives = visible_drives(self.os_name)
        answer = self._call(
            "POST",
            "/poll",
            json={"version": __version__, "hostname": os.environ.get("EDGE_HOSTNAME") or socket.gethostname(), "os": self.os_name, "drives": [drive.report() for drive in self.drives]},
        )
        ALIVE_FILE.touch()
        self._write_state(answer["libraries"])
        return answer

    def _write_state(self, libraries: list[dict]) -> None:
        # The Linux mount helper on the host mounts only these drives when they are plugged in.
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            ids = sorted({library["drive_id"] for library in libraries if library.get("drive_id")})
            (STATE_DIR / "drives").write_text("".join(f"{drive_id}\n" for drive_id in ids), encoding="utf-8")
            (STATE_DIR / "libraries.json").write_text(json.dumps(libraries, indent=2), encoding="utf-8")
        except OSError:
            logger.warning("Could not write the edge state folder", extra={"path": str(STATE_DIR)})

    def run_forever(self) -> None:
        failures = 0
        while True:
            try:
                answer = self.poll()
                failures = 0
            except requests.RequestException as exc:
                wait = BACKOFF[min(failures, len(BACKOFF) - 1)]
                failures += 1
                logger.warning("Server not reachable", extra={"error": str(exc), "retry_in": wait})
                time.sleep(wait)
                continue
            libraries = {library["id"]: library for library in answer["libraries"]}
            if self.running is None:
                job = next((job for job in answer["jobs"] if job["library_id"] in libraries), None)
                if job is not None:
                    self.running = job["id"]
                    # Check-ins go on while a long scan hashes, so the server keeps seeing the device.
                    threading.Thread(target=self._run_job, args=(job, libraries[job["library_id"]]), daemon=True).start()
                elif answer.get("metadata"):
                    self.running = "metadata"
                    threading.Thread(target=self._match, args=(answer["metadata"], answer["provider_order"]), daemon=True).start()
            time.sleep(answer["poll_seconds"])

    def _run_job(self, job: dict, library: dict) -> None:
        try:
            # A scan someone started stores new files; an automatic one (no user) only counts them.
            self.scan(job["id"], library, store_new=job.get("user_id") is not None)
        except Cancelled:
            logger.info("Scan cancelled", extra={"job_id": job["id"]})
        except Exception as exc:
            logger.exception("Scan failed", extra={"job_id": job["id"]})
            try:
                self._call("POST", f"/jobs/{job['id']}/fail", json={"error": f"{type(exc).__name__}: {exc}"[:2000]})
            except requests.RequestException:
                pass
        finally:
            self.running = None

    def _match(self, entries: list[dict], provider_order: list[str]) -> None:
        """Looks the entries up from this machine, which a source may serve when it refuses the server."""
        try:
            service = MetadataService(providers=self._providers(), provider_order=provider_order)
            for entry in entries:
                result, score = service.auto_match(entry["title"])
                details = None
                if result is not None and score >= PARTIAL_THRESHOLD:
                    details = service.get_merged_details(entry["title"], result.provider, result.provider_id)
                self._call("POST", "/metadata", json={
                    "entry_id": entry["entry_id"],
                    "provider": result.provider if result else None,
                    "provider_id": result.provider_id if result else None,
                    "score": score,
                    "details": details.model_dump(mode="json") if details else None,
                })
        except Exception:
            logger.exception("Metadata lookup failed")
        finally:
            self.running = None

    def _providers(self) -> list:
        # IGDB keeps its keys on the server; here it is used only when this device's .env has them.
        providers = [VNDBProvider(), SteamProvider(), *load_plugin_providers()]
        if os.environ.get("TWITCH_CLIENT_ID") and os.environ.get("TWITCH_CLIENT_SECRET"):
            providers.append(IGDBProvider())
        return providers

    def _progress(self, job_id: str, done: int, total: int, details: str) -> None:
        if self._call("POST", f"/jobs/{job_id}/progress", json={"done": done, "total": total, "details": details})["cancelled"]:
            raise Cancelled()

    def scan(self, job_id: str, library: dict, store_new: bool = True) -> None:
        self._progress(job_id, 0, 1, f"Scanning {library['name']} on this device")
        try:
            root, drive, subpath = library_root(self.os_name, library, self.drives)
        except EdgePathError as exc:
            self._send(job_id, {"library_id": library["id"], "error": str(exc), "items": []})
            return
        if not root.is_dir():
            reason = "Drive not connected" if library.get("drive_id") else f"Folder not found: {library['path']}"
            self._send(job_id, {"library_id": library["id"], "error": reason, "items": []})
            return

        items = self.scanner._discover_items(root)
        for item in items:
            item.relative_path = self.scanner._relative_path(item.file_path, root)
        known = self._call("GET", f"/libraries/{library['id']}/state")["entries"]
        pending = []
        if store_new:
            to_hash = [item for item in items if item.archive_type != SUPPORTED_FOLDER_TYPE and self._changed(item, known.get(item.relative_path))]
        else:
            # Only sizes are compared: new or resized files are reported as pending and nothing is hashed.
            unchanged = []
            for item in items:
                (pending if self._resized(item, known.get(item.relative_path)) else unchanged).append(item)
            items, to_hash = unchanged, []
        total = sum(item.file_size or 0 for item in to_hash) or 1
        done, last = 0, 0.0
        for item in to_hash:
            def on_chunk(chunks, start=done):
                nonlocal last
                if time.monotonic() - last >= PROGRESS_EVERY:
                    last = time.monotonic()
                    self._progress(job_id, start + chunks * 1024 * 1024, total, f"Hashing {item.filename}")
            item.file_hash = self.scanner._compute_file_hash(Path(item.file_path), on_chunk)
            done += item.file_size or 0
        self._send(job_id, {
            "library_id": library["id"],
            "drive": {"id": drive.id, "subpath": subpath, "mount": drive.mount} if drive else None,
            "items": [self._item(item) for item in items],
            **({} if store_new else {"pending": [item.relative_path for item in pending]}),
        })

    def _changed(self, item, known: list | None) -> bool:
        if known is None:
            return True
        size, modified, has_hash = known
        stored = datetime.fromisoformat(modified) if modified else None
        return not has_hash or size != item.file_size or stored != item.modified_time

    def _resized(self, item, known: list | None) -> bool:
        return known is None or (item.archive_type != SUPPORTED_FOLDER_TYPE and known[0] != item.file_size)

    def _item(self, item) -> dict:
        data = dataclasses.asdict(item)
        data["modified_time"] = item.modified_time.isoformat() if item.modified_time else None
        return data

    def _send(self, job_id: str, report: dict) -> None:
        body = gzip.compress(json.dumps(report).encode("utf-8"))
        self._call("POST", f"/jobs/{job_id}/report", data=body, headers={"Content-Type": "application/gzip"}, timeout=600)
        logger.info("Scan sent to the server", extra={"job_id": job_id, "items": len(report["items"]), "error": report.get("error")})


def main() -> None:
    setup_logging()
    server = os.environ.get("LUDEXIS_SERVER_URL", "").strip()
    token = os.environ.get("LUDEXIS_EDGE_TOKEN", "").strip()
    if not server or not token:
        raise SystemExit("Set LUDEXIS_SERVER_URL and LUDEXIS_EDGE_TOKEN in the edge .env (from the server: Admin > Edge > Add edge).")
    os_name = os.environ.get("EDGE_OS", "linux").lower()
    logger.info("Edge device started", extra={"server": server, "os": os_name, "version": __version__})
    EdgeAgent(server, token, os_name).run_forever()
