import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class Library(Base):
    __tablename__ = "libraries"
    __allow_unmapped__ = True

    id: str = mapped_column(
        sa.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    name: str = mapped_column(
        sa.String(256),
        nullable=False,
        unique=True,
    )

    path: str = mapped_column(
        sa.Text,
        nullable=False,
        unique=True,
    )

    enabled: bool = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
    )

    created_at = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    updated_at = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )

    deleted_at = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    archive_entries = relationship(
        "ArchiveEntry",
        back_populates="library",
    )