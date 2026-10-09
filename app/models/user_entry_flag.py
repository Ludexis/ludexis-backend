import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

from app.db.base import Base


class UserEntryFlag(Base):
    """One user's favourite and completed marks on a game."""

    __tablename__ = "user_entry_flags"
    __allow_unmapped__ = True

    user_id = mapped_column(sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    archive_entry_id = mapped_column(sa.String(36), sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True)
    favorite: bool = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    completed: bool = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
