import gzip
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from main import app
from app.models.edge_device import EdgeDevice
from app.models.job_history import JobHistory
from app.models.library import Library
from app.services import edge as edge_service
from app.services.edge import EdgeService, drive_key
from app.services.job import JobService
from app.utils.enums import JobStatus, JobType
from tests.test_db import TestingSessionLocal

client = TestClient(app)


@pytest.fixture(autouse=True)
def reports_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(edge_service, "REPORTS_DIR", tmp_path / "edge-reports")


def admin_headers():
    response = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def edge_headers(token):
    return {"Authorization": f"Bearer {token}"}


def add_edge(headers=None):
    response = client.post("/api/edge-devices/", headers=headers or admin_headers(), json={"name": f"Edge-{uuid.uuid4().hex[:8]}"})
    assert response.status_code == 201
    return response.json()


def poll(token, drives=()):
    response = client.post(
        "/api/edge/agent/poll",
        headers=edge_headers(token),
        json={"version": "1.1.0", "hostname": "laptop", "os": "linux", "drives": list(drives)},
    )
    assert response.status_code == 200
    return response.json()


def add_edge_library(headers, edge_id, path="/media/me/Games"):
    response = client.post(
        "/api/libraries/",
        headers=headers,
        json={"name": f"Edge-Library-{uuid.uuid4().hex[:8]}", "path": path, "edge_id": edge_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_new_edge_is_pending_until_it_checks_in():
    headers = admin_headers()
    edge = add_edge(headers)
    assert edge["status"] == "PENDING"
    assert edge["token"].startswith("ldx_")

    poll(edge["token"], [{"id": "1A2B-3C4D", "mount": "/media/me/Games", "label": "Games"}])

    listed = {item["id"]: item for item in client.get("/api/edge-devices/", headers=headers).json()}[edge["id"]]
    assert listed["status"] == "ONLINE"
    assert listed["hostname"] == "laptop"
    assert listed["drives"][0]["label"] == "Games"
    assert "token" not in listed


def test_agent_routes_refuse_user_sessions_and_unknown_tokens():
    assert client.post("/api/edge/agent/poll", headers=admin_headers(), json={"version": "1", "os": "linux"}).status_code == 401
    assert client.post("/api/edge/agent/poll", headers=edge_headers("ldx_nope"), json={"version": "1", "os": "linux"}).status_code == 401


def test_rotating_the_token_revokes_the_old_one():
    headers = admin_headers()
    edge = add_edge(headers)
    rotated = client.post(f"/api/edge-devices/{edge['id']}/token", headers=headers).json()
    assert client.get("/api/edge/agent/libraries", headers=edge_headers(edge["token"])).status_code == 401
    assert client.get("/api/edge/agent/libraries", headers=edge_headers(rotated["token"])).status_code == 200


def test_an_edge_library_is_scanned_by_its_device():
    headers = admin_headers()
    edge = add_edge(headers)
    library = add_edge_library(headers, edge["id"])
    assert library["edge_name"] == edge["name"]

    jobs = poll(edge["token"])["jobs"]
    assert [(job["library_id"], job["status"]) for job in jobs] == [(library["id"], "PENDING")]

    # A second request while the device is away does not pile up scans.
    again = client.post(f"/api/scan/incremental?library_id={library['id']}", headers=headers)
    assert again.status_code == 201
    assert again.json()["id"] == jobs[0]["id"]


def test_another_device_cannot_touch_the_library_or_its_jobs():
    headers = admin_headers()
    owner, other = add_edge(headers), add_edge(headers)
    library = add_edge_library(headers, owner["id"])
    job_id = poll(owner["token"])["jobs"][0]["id"]

    assert client.get(f"/api/edge/agent/libraries/{library['id']}/state", headers=edge_headers(other["token"])).status_code == 404
    assert client.post(f"/api/edge/agent/jobs/{job_id}/fail", headers=edge_headers(other["token"]), json={"error": "x"}).status_code == 404
    assert poll(other["token"])["jobs"] == []


def test_the_same_path_is_allowed_once_per_machine():
    headers = admin_headers()
    first, second = add_edge(headers), add_edge(headers)
    path = f"/media/{uuid.uuid4().hex}"
    add_edge_library(headers, first["id"], path)
    add_edge_library(headers, second["id"], path)
    duplicate = client.post("/api/libraries/", headers=headers, json={"name": f"Dup-{uuid.uuid4().hex[:8]}", "path": path, "edge_id": first["id"]})
    assert duplicate.status_code == 400


def test_a_server_library_is_still_scanned_by_the_server_worker():
    headers = admin_headers()
    library = client.post("/api/libraries/", headers=headers, json={"name": f"Server-{uuid.uuid4().hex[:8]}", "path": f"/games/{uuid.uuid4().hex}"}).json()
    assert library["edge_id"] is None
    job = client.post(f"/api/scan/incremental?library_id={library['id']}", headers=headers).json()
    assert job["task_id"].startswith("test-task-")


def test_progress_reports_cancellation_and_failures_show_on_the_library():
    headers = admin_headers()
    edge = add_edge(headers)
    library = add_edge_library(headers, edge["id"])
    job_id = poll(edge["token"])["jobs"][0]["id"]

    progress = client.post(f"/api/edge/agent/jobs/{job_id}/progress", headers=edge_headers(edge["token"]), json={"done": 5, "total": 10})
    assert progress.json() == {"cancelled": False}
    client.post(f"/api/edge/agent/jobs/{job_id}/fail", headers=edge_headers(edge["token"]), json={"error": "Path not found"})

    stored = client.get(f"/api/libraries/{library['id']}", headers=headers).json()
    assert stored["last_error"] == "Path not found"


def test_a_report_is_stored_by_the_server_worker():
    headers = admin_headers()
    edge = add_edge(headers)
    library = add_edge_library(headers, edge["id"], "/media/me/Report")
    job_id = poll(edge["token"])["jobs"][0]["id"]
    report = {
        "library_id": library["id"],
        "drive": {"id": "0123456789ABCDEF", "subpath": "Report", "mount": "/media/me"},
        "items": [{
            "file_path": "/media/me/Report/Game v1.0.zip", "relative_path": "Game v1.0.zip", "filename": "Game v1.0.zip",
            "archive_name": "Game v1.0", "folder_name": "Report", "title": "Game", "version": "1.0", "archive_type": "ZIP",
            "file_size": 10, "modified_time": "2026-10-01T00:00:00+00:00", "file_hash": "a" * 64,
        }],
    }
    response = client.post(f"/api/edge/agent/jobs/{job_id}/report", headers=edge_headers(edge["token"]), content=gzip.compress(json.dumps(report).encode()))
    assert response.status_code == 202
    assert response.json()["task_id"]

    with TestingSessionLocal() as db:
        stats = EdgeService().ingest(db, job_id)
        stored = db.get(Library, library["id"])
        assert stats["created"] == 1
        assert stored.drive_id == "0123456789ABCDEF"
        assert stored.status == "ONLINE"
    assert not (edge_service.REPORTS_DIR / f"{job_id}.json.gz").exists()
    assert client.post(f"/api/edge/agent/jobs/{job_id}/report", headers=edge_headers(edge["token"]), content=b"x").status_code == 409


def test_connecting_a_known_drive_queues_a_scan_when_autoscan_is_on():
    headers = admin_headers()
    edge = add_edge(headers)
    library = add_edge_library(headers, edge["id"])
    with TestingSessionLocal() as db:
        db.query(JobHistory).filter(JobHistory.library_id == library["id"]).update({"status": JobStatus.SUCCESS})
        db.query(Library).filter(Library.id == library["id"]).update({"drive_id": "0123456789ABCDEF"})
        db.commit()

    assert poll(edge["token"])["jobs"] == []
    # Windows names the same NTFS drive by its low 32 bits.
    jobs = poll(edge["token"], [{"id": "89ABCDEF", "mount": "/drives/E"}])["jobs"]
    assert [job["library_id"] for job in jobs] == [library["id"]]
    assert drive_key("0123-4567-89AB-CDEF") == drive_key("89abcdef")


def test_edge_jobs_never_block_or_get_failed_by_the_server_worker():
    headers = admin_headers()
    edge = add_edge(headers)
    add_edge_library(headers, edge["id"])
    job_id = poll(edge["token"])["jobs"][0]["id"]
    client.post(f"/api/edge/agent/jobs/{job_id}/progress", headers=edge_headers(edge["token"]), json={"done": 1, "total": 10})

    with TestingSessionLocal() as db:
        JobService().fail_stale_jobs(db, worker_restarted=True)
        assert db.get(JobHistory, job_id).status == JobStatus.RUNNING
        assert all(job.edge_id is None for job in [JobService().active_job(db, JobType.INCREMENTAL_SCAN)] if job)

        # A device that stops checking in loses the job it was running.
        db.query(EdgeDevice).filter(EdgeDevice.id == edge["id"]).update({"last_seen_at": datetime.now(UTC) - timedelta(hours=2)})
        db.commit()
        JobService().fail_stale_jobs(db)
        assert db.get(JobHistory, job_id).status == JobStatus.FAILED


def test_removing_an_edge_keeps_its_libraries_on_the_server():
    headers = admin_headers()
    edge = add_edge(headers)
    library = add_edge_library(headers, edge["id"])
    job_id = poll(edge["token"])["jobs"][0]["id"]

    assert client.delete(f"/api/edge-devices/{edge['id']}", headers=headers).status_code == 204

    stored = client.get(f"/api/libraries/{library['id']}", headers=headers).json()
    assert stored["edge_id"] is None
    with TestingSessionLocal() as db:
        assert db.get(JobHistory, job_id).status == JobStatus.CANCELED


def test_a_device_that_matches_metadata_gets_its_new_entries_and_stores_the_results(monkeypatch):
    from app.services import edge as edge_module

    monkeypatch.setattr(edge_module.ArtworkService, "fill_missing_artwork", lambda self, db, entry, **kwargs: 0)
    headers = admin_headers()
    edge = add_edge(headers)
    client.patch(f"/api/edge-devices/{edge['id']}", headers=headers, json={"match_metadata": True})
    library = add_edge_library(headers, edge["id"], f"/media/{uuid.uuid4().hex}")
    with TestingSessionLocal() as db:
        from app.models.archive_entry import ArchiveEntry
        from app.utils.enums import MetadataStatus, VerificationStatus

        for title in ("Edge Matched", "Edge Unknown"):
            db.add(ArchiveEntry(title=title, file_path=f"/m/{uuid.uuid4().hex}.zip", library_id=library["id"],
                                metadata_status=MetadataStatus.UNMATCHED, verification_status=VerificationStatus.UNKNOWN))
        db.commit()

    requests = {item["title"]: item["entry_id"] for item in poll(edge["token"])["metadata"]}
    assert set(requests) == {"Edge Matched", "Edge Unknown"}

    details = {"provider": "VNDB", "provider_id": "v1", "title": "Edge Matched", "genres": ["Adventure"], "restricted": True}
    send = lambda body: client.post("/api/edge/agent/metadata", headers=edge_headers(edge["token"]), json=body)
    assert send({"entry_id": requests["Edge Matched"], "provider": "VNDB", "provider_id": "v1", "score": 0.95, "details": details}).status_code == 204
    assert send({"entry_id": requests["Edge Unknown"], "score": 0.4}).status_code == 204

    with TestingSessionLocal() as db:
        matched, unknown = (db.get(ArchiveEntry, requests[title]) for title in ("Edge Matched", "Edge Unknown"))
        assert (matched.metadata_status, matched.metadata_source_code, matched.restricted) == (MetadataStatus.MATCHED, "v1", True)
        assert [genre.name for genre in matched.genres] == ["Adventure"]
        assert unknown.metadata_status == MetadataStatus.UNMATCHED and unknown.last_metadata_refresh is not None
    # Both were tried, so they are not handed out again.
    assert poll(edge["token"])["metadata"] == []
    other = add_edge(headers)
    assert client.post("/api/edge/agent/metadata", headers=edge_headers(other["token"]), json={"entry_id": requests["Edge Unknown"]}).status_code == 404
