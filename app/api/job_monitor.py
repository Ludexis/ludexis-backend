from fastapi import APIRouter, Depends

from app.core.auth import require_permission
from app.core.auth import PermissionName
from app.services.job_monitor import JobMonitorService

router = APIRouter(
    prefix="/job-monitor",
    tags=["job-monitor"],
)

monitor = JobMonitorService()


@router.get(
    "/workers",
    summary="List Celery workers",
    description="Return connected Celery workers.",
)
def list_workers(
    current_user=Depends(
        require_permission(
            PermissionName.ACCESS_ADMIN
        )
    ),
):
    return monitor.workers()


@router.get(
    "/stats",
    summary="Job queue statistics",
    description="Return worker and task statistics.",
)
def queue_stats(
    current_user=Depends(
        require_permission(
            PermissionName.ACCESS_ADMIN
        )
    ),
):
    return monitor.stats()