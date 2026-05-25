import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __allow_unmapped__ = True

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = mapped_column(sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: str = mapped_column(sa.String(128), nullable=False)
    entity: str = mapped_column(sa.String(128), nullable=False)
    entity_id: str = mapped_column(sa.String(36), nullable=True)
    details: str = mapped_column(sa.Text, nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    user = relationship("User")
