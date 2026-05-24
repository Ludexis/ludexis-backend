import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class MetadataSource(Base):
    __tablename__ = "metadata_sources"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_name: str = mapped_column(sa.String(128), unique=True, nullable=False)
    description: str = mapped_column(sa.Text, nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    archive_entries = relationship("ArchiveEntry", back_populates="metadata_source")
