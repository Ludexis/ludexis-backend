import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class Screenshot(Base):
    __tablename__ = "screenshots"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    archive_entry_id = mapped_column(sa.String(36), sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), nullable=False)
    file_path: str = mapped_column(sa.Text, nullable=False)
    caption: str = mapped_column(sa.String(256), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    archive_entry = relationship("ArchiveEntry", back_populates="screenshots")
