from sqlalchemy.orm import Session

from app.repositories.audit_log import AuditLogRepository


class AuditLogService:
    def __init__(self) -> None:
        self.repo = AuditLogRepository()

    def log(
        self,
        db: Session,
        action: str,
        entity: str,
        entity_id: str | None = None,
        user_id: str | None = None,
        details: str | None = None,
    ):
        return self.repo.create(
            db,
            {
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "user_id": user_id,
                "details": details,
            },
        )