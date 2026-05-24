import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class Publisher(Base):
    __tablename__ = "publishers"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = mapped_column(sa.String(256), unique=True, nullable=False)
    description: str = mapped_column(sa.Text, nullable=True)
    website: str = mapped_column(sa.String(256), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    archive_entries = relationship("ArchiveEntry", secondary="archive_entry_publishers", back_populates="publishers")
