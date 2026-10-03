from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.job_history import JobHistory
from app.models.system import ScheduledTask
from app.models.user import User
from app.utils.enums import JobType

logger = get_logger(__name__)

# key: (name, job type, hour, minute, day of week or None for daily)
DEFAULT_TASKS = {
    # The incremental scan also re-checks offline libraries: one that is back gets a full rescan.
    "library_scan": ("Scan libraries", JobType.INCREMENTAL_SCAN, 2, 0, None),
    "metadata_refresh": ("Refresh metadata", JobType.METADATA_REFRESH, 3, 0, None),
    "artwork_validation": ("Validate artwork", JobType.ARTWORK_REFRESH, 4, 0, None),
    "integrity_verification": ("Verify archive integrity", JobType.INTEGRITY_VERIFICATION, 5, 0, 6),
    "duplicate_detection": ("Detect duplicates", JobType.DUPLICATE_DETECTION, 5, 30, 6),
}


def now_local() -> datetime:
    # Schedules follow the server's local time (the TZ variable in Docker).
    return datetime.now().astimezone()


def last_occurrence(task: ScheduledTask, now: datetime) -> datetime:
    candidate = now.replace(hour=task.hour, minute=task.minute, second=0, microsecond=0)
    if task.day_of_week is None:
        if candidate > now:
            candidate -= timedelta(days=1)
    else:
        candidate -= timedelta(days=(candidate.weekday() - task.day_of_week) % 7)
        if candidate > now:
            candidate -= timedelta(days=7)
    return candidate


class SchedulerService:
    def list_tasks(self, db: Session) -> list[ScheduledTask]:
        existing = {task.key: task for task in db.query(ScheduledTask).all()}
        for key, (_, job_type, hour, minute, day_of_week) in DEFAULT_TASKS.items():
            if key not in existing:
                # Starting the clock now keeps a fresh install from running every task at once.
                existing[key] = ScheduledTask(
                    key=key, job_type=job_type.value, enabled=True, hour=hour, minute=minute,
                    day_of_week=day_of_week, last_run_at=now_local(),
                )
                db.add(existing[key])
        db.commit()
        return [existing[key] for key in DEFAULT_TASKS]

    def get(self, db: Session, key: str) -> ScheduledTask | None:
        if key not in DEFAULT_TASKS:
            return None
        return next(task for task in self.list_tasks(db) if task.key == key)

    def update(self, db: Session, task: ScheduledTask, data: dict) -> ScheduledTask:
        for field, value in data.items():
            setattr(task, field, value)
        db.commit()
        return task

    def describe(self, db: Session, task: ScheduledTask) -> dict:
        job = db.get(JobHistory, task.last_job_id) if task.last_job_id else None
        return {
            "key": task.key,
            "name": DEFAULT_TASKS[task.key][0],
            "job_type": task.job_type,
            "enabled": task.enabled,
            "hour": task.hour,
            "minute": task.minute,
            "day_of_week": task.day_of_week,
            "last_run_at": task.last_run_at,
            "last_job_id": task.last_job_id,
            "last_job_status": job.status.value if job else None,
            "next_run_at": last_occurrence(task, now_local()) + (timedelta(days=1) if task.day_of_week is None else timedelta(days=7)),
        }

    def run(self, db: Session, task: ScheduledTask, user: User | None = None) -> JobHistory:
        from app.services.job import JobService

        job = JobService().start_job(db, user, JobType(task.job_type), details=f"Scheduled task: {DEFAULT_TASKS[task.key][0]}")
        task.last_run_at = now_local()
        task.last_job_id = job.id
        db.commit()
        return job

    def tick(self, db: Session) -> list[str]:
        """Start every enabled task whose time has passed since it last ran."""
        from app.services.job import JobService

        started = []
        now = now_local()
        jobs = JobService()
        for task in self.list_tasks(db):
            if not task.enabled or (task.last_run_at and task.last_run_at >= last_occurrence(task, now)):
                continue
            # A job of the same type already running counts; the task is retried at the next tick.
            if jobs.active_job(db, JobType(task.job_type)):
                continue
            self.run(db, task)
            started.append(task.key)
        if started:
            logger.info("Scheduled tasks started", extra={"tasks": started})
        return started
