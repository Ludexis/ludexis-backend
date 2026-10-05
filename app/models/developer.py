import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship, validates

from app.db.base import Base
from app.utils.normalization import company_key


class Developer(Base):
    __tablename__ = "developers"
    __allow_unmapped__ = True
    __table_args__ = (
        sa.Index("ix_developers_name_trgm", "name", postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
    )

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = mapped_column(sa.String(256), unique=True, nullable=False)
    # Spelling-independent form of the name, so "SEGA" and "Sega" are one record.
    name_key: str = mapped_column(sa.String(256), unique=True, nullable=False)
    description: str = mapped_column(sa.Text, nullable=True)
    website: str = mapped_column(sa.String(256), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    archive_entries = relationship("ArchiveEntry", secondary="archive_entry_developers", back_populates="developers")

    @validates("name")
    def _set_name_key(self, _key, name):
        self.name_key = company_key(name)
        return name
