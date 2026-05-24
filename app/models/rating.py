import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class Rating(Base):
    __tablename__ = "ratings"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = mapped_column(sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    archive_entry_id = mapped_column(sa.String(36), sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), nullable=False)
    score: int = mapped_column(sa.Integer, nullable=False)
    review: str = mapped_column(sa.Text, nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    user = relationship("User", back_populates="ratings")
    archive_entry = relationship("ArchiveEntry", back_populates="ratings")
