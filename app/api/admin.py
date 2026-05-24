from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.admin import AdminStats
from app.schemas.audit_log import AuditLogRead
from app.services.admin import AdminService
from app.services.audit import AuditService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/admin", tags=["admin"])
admin_service = AdminService()
audit_service = AuditService()


@router.get("/audit-logs", response_model=list[AuditLogRead])
def read_audit_logs(
    user_id: str | None = None,
    entity: str | None = None,
    action: str | None = None,
    offset: int = 0,
    limit: int = 100,
    current_user=Depends(require_permission(PermissionName.VIEW_AUDIT_LOGS)),
    db: Session = Depends(get_db),
):
    return audit_service.list_logs(db, user_id=user_id, entity=entity, action=action, offset=offset, limit=limit)


@router.get("/stats", response_model=AdminStats)
def read_admin_stats(
    current_user=Depends(require_permission(PermissionName.ACCESS_ADMIN)),
    db: Session = Depends(get_db),
):
    return admin_service.get_stats(db)
