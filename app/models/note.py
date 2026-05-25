import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class Note(Base):
    __tablename__ = "notes"
    __allow_unmapped__ = True

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = mapped_column(sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archive_entry_id = mapped_column(sa.String(36), sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), nullable=False)
    content: str = mapped_column(sa.Text, nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    user = relationship("User", back_populates="notes")
    archive_entry = relationship("ArchiveEntry", back_populates="notes")
