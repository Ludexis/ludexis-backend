import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class Franchise(Base):
    __tablename__ = "franchises"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = mapped_column(sa.String(256), unique=True, nullable=False)
    description: str = mapped_column(sa.Text, nullable=True)
    banner_path: str = mapped_column(sa.Text, nullable=True)
    parent_id = mapped_column(sa.String(36), sa.ForeignKey("franchises.id", ondelete="SET NULL"), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    parent = relationship("Franchise", remote_side=[id], backref="child_franchises")
    archive_entries = relationship("ArchiveEntry", back_populates="franchise")

    @property
    def child_ids(self) -> list[str]:
        return [child.id for child in self.child_franchises]
