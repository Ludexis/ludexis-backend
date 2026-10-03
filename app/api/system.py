from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.session import get_db
from app.schemas.job_history import JobHistoryRead
from app.schemas.system import ScheduledTaskRead, ScheduledTaskUpdate, SettingsRead, SettingsUpdate
from app.services.audit import AuditService
from app.services.scheduler import SchedulerService
from app.services.settings import MATCH_PROVIDERS, SettingsService
from app.utils.audit_actions import AuditAction
from app.utils.enums import PermissionName

router = APIRouter(prefix="/admin", tags=["admin"])
scheduler = SchedulerService()
settings_service = SettingsService()
audit_service = AuditService()


def _task_or_404(db: Session, key: str):
    task = scheduler.get(db, key)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled task not found")
    return task


@router.get("/scheduled-tasks", response_model=list[ScheduledTaskRead], summary="List scheduled tasks")
def list_scheduled_tasks(current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)), db: Session = Depends(get_db)):
    return [scheduler.describe(db, task) for task in scheduler.list_tasks(db)]


@router.patch("/scheduled-tasks/{key}", response_model=ScheduledTaskRead, summary="Update a scheduled task")
def update_scheduled_task(key: str, payload: ScheduledTaskUpdate, current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)), db: Session = Depends(get_db)):
    task = _task_or_404(db, key)
    data = payload.model_dump(exclude_unset=True)
    if data.get("day_of_week") == -1:
        data["day_of_week"] = None
    scheduler.update(db, task, data)
    audit_service.record(db, current_user, AuditAction.UPDATE_SCHEDULED_TASK, "scheduled_task", key, details=str(data))
    return scheduler.describe(db, task)


@router.post("/scheduled-tasks/{key}/run", response_model=JobHistoryRead, status_code=status.HTTP_202_ACCEPTED, summary="Run a scheduled task now")
def run_scheduled_task(key: str, current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)), db: Session = Depends(get_db)):
    task = _task_or_404(db, key)
    job = scheduler.run(db, task, current_user)
    audit_service.record(db, current_user, AuditAction.RUN_SCHEDULED_TASK, "scheduled_task", key, details=f"job {job.id}")
    return job


@router.get("/settings", response_model=SettingsRead, summary="Get server settings")
def read_settings(current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)), db: Session = Depends(get_db)):
    return settings_service.public(db)


@router.patch("/settings", response_model=SettingsRead, summary="Update server settings")
def update_settings(payload: SettingsUpdate, current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)), db: Session = Depends(get_db)):
    data = payload.model_dump(exclude_unset=True)
    if "provider_order" in data:
        unknown = set(data["provider_order"]) - set(MATCH_PROVIDERS)
        if unknown:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown providers: {sorted(unknown)}")
        data["provider_order"] = list(dict.fromkeys(data["provider_order"]))
    for key, value in data.items():
        settings_service.set(db, key, value)
    changed = sorted(key for key in data if key != "igdb_client_secret") + (["igdb_client_secret"] if "igdb_client_secret" in data else [])
    audit_service.record(db, current_user, AuditAction.UPDATE_SETTINGS, "settings", details=", ".join(changed))
    return settings_service.public(db)
