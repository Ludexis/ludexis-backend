from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from sqlalchemy.orm import Session


class AuditService:
    def __init__(self) -> None:
        self.repo = AuditLogRepository()

    def record(
        self,
        db: Session,
        user: User | None,
        action: str,
        entity: str,
        entity_id: str | None = None,
        details: str | None = None,
    ):
        return self.repo.create(db, {
            "user_id": user.id if user else None,
            "action": action,
            "entity": entity,
            "entity_id": entity_id,
            "details": details,
        })

    def list_logs(self, db: Session, user_id: str | None = None, entity: str | None = None, action: str | None = None, offset: int = 0, limit: int = 100):
        return self.repo.list(db, user_id=user_id, entity=entity, action=action, offset=offset, limit=limit)
