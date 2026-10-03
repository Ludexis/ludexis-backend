from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.job_history import JobHistory
from app.models.system import ScheduledTask
from app.services.scheduler import SchedulerService, last_occurrence, now_local
from app.utils.enums import JobStatus
from main import app
from tests.test_db import TestingSessionLocal

client = TestClient(app)
UTC = timezone.utc


@pytest.fixture
def db():
    session = TestingSessionLocal()
    yield session
    session.close()


def admin_headers():
    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_last_occurrence_daily_and_weekly():
    now = datetime(2026, 10, 7, 1, 30, tzinfo=UTC)  # a Wednesday
    assert last_occurrence(ScheduledTask(hour=2, minute=0, day_of_week=None), now) == datetime(2026, 10, 6, 2, 0, tzinfo=UTC)
    assert last_occurrence(ScheduledTask(hour=1, minute=0, day_of_week=None), now) == datetime(2026, 10, 7, 1, 0, tzinfo=UTC)
    assert last_occurrence(ScheduledTask(hour=5, minute=0, day_of_week=6), now) == datetime(2026, 10, 4, 5, 0, tzinfo=UTC)


def test_tick_starts_due_tasks_once(db):
    service = SchedulerService()
    # Jobs left queued by other tests have no worker; settle them so they do not block the tick.
    db.query(JobHistory).filter(JobHistory.status.in_([JobStatus.PENDING, JobStatus.RUNNING])).update(
        {JobHistory.status: JobStatus.CANCELED}, synchronize_session=False
    )
    tasks = {task.key: task for task in service.list_tasks(db)}
    for task in tasks.values():
        task.last_run_at = now_local()
    tasks["library_scan"].last_run_at = now_local() - timedelta(days=2)
    db.commit()

    assert service.tick(db) == ["library_scan"]
    db.refresh(tasks["library_scan"])
    job = db.get(JobHistory, tasks["library_scan"].last_job_id)
    assert job.job_type.value == "INCREMENTAL_SCAN"

    # The job is still pending, and the task already ran for this slot.
    assert service.tick(db) == []
    job.status = JobStatus.SUCCESS
    db.commit()


def test_scheduled_tasks_api(db):
    headers = admin_headers()
    tasks = client.get("/api/admin/scheduled-tasks", headers=headers).json()
    assert [task["key"] for task in tasks] == [
        "library_scan", "metadata_refresh", "artwork_validation", "integrity_verification", "duplicate_detection",
    ]

    updated = client.patch("/api/admin/scheduled-tasks/metadata_refresh", json={"hour": 1, "minute": 15, "enabled": False}, headers=headers).json()
    assert (updated["hour"], updated["minute"], updated["enabled"]) == (1, 15, False)
    weekly = client.patch("/api/admin/scheduled-tasks/duplicate_detection", json={"day_of_week": -1}, headers=headers).json()
    assert weekly["day_of_week"] is None

    run = client.post("/api/admin/scheduled-tasks/metadata_refresh/run", headers=headers)
    assert run.status_code == 202
    assert client.get("/api/admin/scheduled-tasks", headers=headers).json()[1]["last_job_id"] == run.json()["id"]
    assert client.post("/api/admin/scheduled-tasks/nope/run", headers=headers).status_code == 404
    client.patch("/api/admin/scheduled-tasks/metadata_refresh", json={"hour": 3, "minute": 0, "enabled": True}, headers=headers)
    client.patch("/api/admin/scheduled-tasks/duplicate_detection", json={"day_of_week": 6}, headers=headers)


def test_settings_round_trip_hides_secret(db):
    headers = admin_headers()
    response = client.patch("/api/admin/settings", json={
        "server_name": "Basement Shelf",
        "provider_order": ["IGDB", "VNDB", "IGDB"],
        "igdb_client_id": "client-123",
        "igdb_client_secret": "very-secret",
    }, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["server_name"] == "Basement Shelf"
    assert body["provider_order"] == ["IGDB", "VNDB"]
    assert body["igdb_configured"] is True
    assert "very-secret" not in response.text

    assert client.patch("/api/admin/settings", json={"provider_order": ["Nope"]}, headers=headers).status_code == 422
    client.patch("/api/admin/settings", json={
        "server_name": "Ludexis", "provider_order": ["VNDB", "IGDB", "Steam"], "igdb_client_id": "", "igdb_client_secret": "",
    }, headers=headers)


def test_settings_require_admin():
    token = client.post("/api/auth/login", json={"username": "testuser", "password": "Test123!"}).json()["access_token"]
    assert client.get("/api/admin/settings", headers={"Authorization": f"Bearer {token}"}).status_code == 403

