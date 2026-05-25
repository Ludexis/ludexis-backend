import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base
from app.models.association_tables import (
    archive_entry_developers,
    archive_entry_genres,
    archive_entry_publishers,
    archive_entry_relations,
    archive_entry_tags,
    collection_entries,
    franchise_entries,
)
from app.utils.enums import MetadataStatus, VerificationStatus


class ArchiveEntry(Base):
    __tablename__ = "archive_entries"
    __allow_unmapped__ = True

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: str = mapped_column(sa.String(256), nullable=False)
    description: str = mapped_column(sa.Text, nullable=True)
    version: str = mapped_column(sa.String(64), nullable=True)
    engine: str = mapped_column(sa.String(128), nullable=True)
    release_date = mapped_column(sa.Date, nullable=True)
    archive_type: str = mapped_column(sa.String(64), nullable=True)
    file_path: str = mapped_column(sa.Text, nullable=False)
    storage_device: str = mapped_column(sa.String(128), nullable=True)
    cover_path: str = mapped_column(sa.Text, nullable=True)
    banner_path: str = mapped_column(sa.Text, nullable=True)
    logo_path: str = mapped_column(sa.Text, nullable=True)
    metadata_status: MetadataStatus = mapped_column(sa.Enum(MetadataStatus, name="metadata_status"), nullable=False, default=MetadataStatus.UNMATCHED)
    metadata_source_id = mapped_column(sa.String(36), sa.ForeignKey("metadata_sources.id", ondelete="SET NULL"), nullable=True)
    metadata_source: str = mapped_column(sa.String(128), nullable=True)
    metadata_source_code: str = mapped_column(sa.String(128), nullable=True)
    last_metadata_refresh = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_verified = mapped_column(sa.DateTime(timezone=True), nullable=True)
    verification_status: VerificationStatus = mapped_column(sa.Enum(VerificationStatus, name="verification_status"), nullable=False, default=VerificationStatus.UNKNOWN)
    parent_series_id = mapped_column(sa.String(36), sa.ForeignKey("archive_entries.id", ondelete="SET NULL"), nullable=True)
    franchise_id = mapped_column(sa.String(36), sa.ForeignKey("franchises.id", ondelete="SET NULL"), nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at = mapped_column(sa.DateTime(timezone=True), nullable=True)

    genres = relationship("Genre", secondary=archive_entry_genres, back_populates="archive_entries")
    tags = relationship("Tag", secondary=archive_entry_tags, back_populates="archive_entries")
    developers = relationship("Developer", secondary=archive_entry_developers, back_populates="archive_entries")
    publishers = relationship("Publisher", secondary=archive_entry_publishers, back_populates="archive_entries")
    collections = relationship("Collection", secondary=collection_entries, back_populates="archive_entries")
    franchise = relationship("Franchise", back_populates="archive_entries")
    screenshots = relationship("Screenshot", back_populates="archive_entry", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="archive_entry", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="archive_entry", cascade="all, delete-orphan")
    metadata_source_rel = relationship("MetadataSource", back_populates="archive_entries")
    parent_series = relationship("ArchiveEntry", remote_side=[id], backref="child_entries")
    related_entries = relationship(
        "ArchiveEntry",
        secondary=archive_entry_relations,
        primaryjoin=id == archive_entry_relations.c.source_entry_id,
        secondaryjoin=id == archive_entry_relations.c.target_entry_id,
        backref="related_to_entries",
    )
