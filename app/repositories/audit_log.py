from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self) -> None:
        super().__init__(AuditLog)

    def list(self, db: Session, user_id: str | None = None, entity: str | None = None, action: str | None = None, offset: int = 0, limit: int = 100) -> list[AuditLog]:
        query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
        if user_id is not None:
            query = query.filter(AuditLog.user_id == user_id)
        if entity is not None:
            query = query.filter(AuditLog.entity == entity)
        if action is not None:
            query = query.filter(AuditLog.action == action)
        return query.offset(offset).limit(limit).all()
