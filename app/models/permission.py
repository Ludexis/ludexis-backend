import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class Permission(Base):
    __tablename__ = "permissions"
    __allow_unmapped__ = True

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = mapped_column(sa.String(64), unique=True, nullable=False)
    description: str = mapped_column(sa.Text, nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
