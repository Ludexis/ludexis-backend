import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base
from app.models.association_tables import collection_entries


class Collection(Base):
    __tablename__ = "collections"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = mapped_column(sa.String(256), nullable=False)
    description: str = mapped_column(sa.Text, nullable=True)
    cover_path: str = mapped_column(sa.Text, nullable=True)
    banner_path: str = mapped_column(sa.Text, nullable=True)
    visibility: str = mapped_column(sa.String(32), nullable=False, default="public")
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at = mapped_column(sa.DateTime(timezone=True), nullable=True)

    archive_entries = relationship("ArchiveEntry", secondary=collection_entries, back_populates="collections")

    @property
    def entry_ids(self) -> list[str]:
        return [entry.id for entry in self.archive_entries]
