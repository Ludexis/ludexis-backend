from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

JOB_STATUS_PENDING = "PENDING"
JOB_STATUS_CANCELED = "CANCELED"
JOB_TYPE_DUPLICATE_DETECTION = "DUPLICATE_DETECTION"


def admin_token():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin123!",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def user_token():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "testuser",
            "password": "Test123!",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_full_scan_returns_pending_job():
    token = admin_token()
    response = client.post(
        "/api/scan/full",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["id"]
    assert body["status"] == JOB_STATUS_PENDING


def test_incremental_scan_returns_created():
    token = admin_token()
    response = client.post(
        "/api/scan/incremental",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["status"] == JOB_STATUS_PENDING


def test_get_job_by_id_matches_created_job():
    token = admin_token()
    created = client.post(
        "/api/scan/full",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    response = client.get(
        f"/api/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == job_id


def test_scan_status_returns_expected_keys():
    token = admin_token()
    response = client.get(
        "/api/scan/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    for key in ("pending", "running", "success", "failed", "canceled", "total"):
        assert key in body
        assert isinstance(body[key], int)


def test_start_job_with_duplicate_detection_returns_pending():
    token = admin_token()
    response = client.post(
        "/api/jobs/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_type": JOB_TYPE_DUPLICATE_DETECTION},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["job_type"] == JOB_TYPE_DUPLICATE_DETECTION
    assert body["status"] == JOB_STATUS_PENDING


def test_cancel_pending_job_sets_canceled():
    token = admin_token()
    created = client.post(
        "/api/scan/full",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert created.status_code == 201
    job_id = created.json()["id"]

    response = client.post(
        f"/api/jobs/{job_id}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == job_id
    assert response.json()["status"] == JOB_STATUS_CANCELED


def test_cancel_nonexistent_job_returns_404():
    token = admin_token()
    response = client.post(
        "/api/jobs/nonexistent-job-id/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_list_jobs_filtered_by_status_canceled():
    token = admin_token()
    response = client.get(
        "/api/jobs/",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": JOB_STATUS_CANCELED},
    )
    assert response.status_code == 200
    jobs = response.json()
    assert isinstance(jobs, list)
    for job in jobs:
        assert job["status"] == JOB_STATUS_CANCELED


def test_job_monitor_stats_returns_expected_shape():
    token = admin_token()
    response = client.get(
        "/api/job-monitor/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    for key in ("workers", "active_tasks", "reserved_tasks"):
        assert key in body
        assert isinstance(body[key], int)


def test_job_monitor_workers_returns_dict():
    token = admin_token()
    response = client.get(
        "/api/job-monitor/workers",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert isinstance(response.json(), dict)


def test_rbac_scan_full_denied_for_user():
    token = user_token()
    response = client.post(
        "/api/scan/full",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_rbac_jobs_start_denied_for_user():
    token = user_token()
    response = client.post(
        "/api/jobs/start",
        headers={"Authorization": f"Bearer {token}"},
        json={"job_type": JOB_TYPE_DUPLICATE_DETECTION},
    )
    assert response.status_code == 403


def test_rbac_jobs_cancel_denied_for_user():
    token = user_token()
    response = client.post(
        "/api/jobs/some-job-id/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_rbac_job_monitor_stats_denied_for_user():
    token = user_token()
    response = client.get(
        "/api/job-monitor/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_rbac_jobs_list_allowed_for_user():
    token = user_token()
    response = client.get(
        "/api/jobs/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_unauthenticated_scan_full_returns_401():
    response = client.post("/api/scan/full")
    assert response.status_code == 401


def test_job_start_and_cancel_are_audited():
    headers = {"Authorization": f"Bearer {admin_token()}"}
    job = client.post("/api/jobs/start", headers=headers, json={"job_type": JOB_TYPE_DUPLICATE_DETECTION}).json()
    client.post(f"/api/jobs/{job['id']}/cancel", headers=headers)

    logs = client.get("/api/admin/audit-logs?entity=JobHistory&limit=500", headers=headers).json()

    actions = {log["action"] for log in logs if log["entity_id"] == job["id"]}
    assert actions == {"START_JOB", "CANCEL_JOB"}


def test_scan_of_one_library_passes_it_to_the_task(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from celery.app.task import Task

    token = admin_token()
    headers = {"Authorization": f"Bearer {token}"}
    library = client.post("/api/libraries/", json={"name": f"Skybound {tmp_path.name}", "path": str(tmp_path)}, headers=headers)
    assert library.status_code == 201
    queued = []
    monkeypatch.setattr(Task, "apply_async", lambda self, *args, **kwargs: queued.append(kwargs) or SimpleNamespace(id="t1"))

    response = client.post(f"/api/scan/incremental?library_id={library.json()['id']}", headers=headers)

    assert response.status_code == 201
    assert queued[0]["kwargs"] == {"library_id": library.json()["id"]}
    assert client.post("/api/scan/full?library_id=no-such-library", headers=headers).status_code == 404
