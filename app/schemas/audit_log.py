from datetime import datetime

from pydantic import BaseModel


class AuditLogBase(BaseModel):
    user_id: str | None = None
    action: str
    entity: str
    entity_id: str | None = None
    details: str | None = None


class AuditLogRead(AuditLogBase):
    id: str
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
