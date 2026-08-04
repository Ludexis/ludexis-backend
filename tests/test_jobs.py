from unittest.mock import Mock, patch
from tests.test_db import TestingSessionLocal
from app.models.user import User
from app.services.job import JobService
from app.utils.enums import JobStatus, JobType

def get_admin_user(db):
    return (
        db.query(User)
        .filter(User.username == "admin")
        .first()
    )


def test_start_job_creates_pending_job():
    db = TestingSessionLocal()
    service = JobService()
    user = get_admin_user(db)
    fake_task = Mock()
    fake_task.id = "pytest-task-id"
    with patch.object(
        service,
        "_select_task",
    ) as mock_select:
        mock_select.return_value.apply_async.return_value = (
            fake_task
        )
        job = service.start_job(
            db,
            user,
            JobType.LIBRARY_SCAN,
        )
    assert job is not None
    assert job.status == JobStatus.PENDING
    assert job.task_id == "pytest-task-id"
    db.close()


def test_get_job():
    db = TestingSessionLocal()
    service = JobService()
    user = get_admin_user(db)
    fake_task = Mock()
    fake_task.id = "pytest-task-id"
    with patch.object(
        service,
        "_select_task",
    ) as mock_select:
        mock_select.return_value.apply_async.return_value = (
            fake_task
        )
        created = service.start_job(
            db,
            user,
            JobType.LIBRARY_SCAN,
        )
    fetched = service.get_job(
        db,
        created.id,
    )
    assert fetched is not None
    assert fetched.id == created.id
    db.close()


def test_cancel_pending_job():
    db = TestingSessionLocal()
    service = JobService()
    user = get_admin_user(db)
    fake_task = Mock()
    fake_task.id = "pytest-task-id"
    with patch.object(
        service,
        "_select_task",
    ) as mock_select:
        mock_select.return_value.apply_async.return_value = (
            fake_task
        )
        job = service.start_job(
            db,
            user,
            JobType.LIBRARY_SCAN,
        )
    cancelled = service.cancel_job(
        db,
        job.id,
    )
    assert cancelled.status == JobStatus.CANCELED
    db.close()


def test_cancel_invalid_job():
    db = TestingSessionLocal()
    service = JobService()
    result = service.cancel_job(
        db,
        "does-not-exist",
    )
    assert result is None
    db.close()


def test_cancel_completed_job_does_nothing():
    db = TestingSessionLocal()
    service = JobService()
    user = get_admin_user(db)
    fake_task = Mock()
    fake_task.id = "pytest-task-id"
    with patch.object(
        service,
        "_select_task",
    ) as mock_select:
        mock_select.return_value.apply_async.return_value = (
            fake_task
        )
        job = service.start_job(
            db,
            user,
            JobType.LIBRARY_SCAN,
        )
    job.status = JobStatus.SUCCESS
    db.add(job)
    db.commit()
    result = service.cancel_job(
        db,
        job.id,
    )
    assert result.status == JobStatus.SUCCESS
    db.close()