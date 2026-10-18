import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class Library(Base):
    __tablename__ = "libraries"
    __allow_unmapped__ = True
    # One path per machine: the server and each edge device have their own folders.
    __table_args__ = (
        sa.Index("uq_libraries_location_path", sa.func.coalesce(sa.text("edge_id"), ""), "path", unique=True),
    )

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

    # On an edge device, the path as that machine shows it (/media/me/Games, Z:\Games).
    path: str = mapped_column(
        sa.Text,
        nullable=False,
    )

    enabled: bool = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
    )

    status: str = mapped_column(sa.String(16), nullable=False, default="ONLINE", server_default="ONLINE")
    last_seen_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_scan_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_error: str = mapped_column(sa.Text, nullable=True)

    # Empty: the server scans this library. Otherwise the edge device that has the drive.
    edge_id = mapped_column(sa.String(36), sa.ForeignKey("edge_devices.id", ondelete="SET NULL"), nullable=True, index=True)
    # Filesystem UUID or volume serial of the drive, its folder below the drive's root and where it was last mounted;
    # learnt at the first scan, so the library is found again wherever the drive is mounted next.
    drive_id: str = mapped_column(sa.String(64), nullable=True)
    drive_subpath: str = mapped_column(sa.Text, nullable=True)
    drive_mount: str = mapped_column(sa.Text, nullable=True)

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

    edge = relationship("EdgeDevice", back_populates="libraries")

    @property
    def edge_name(self) -> str | None:
        return self.edge.name if self.edge is not None else None

    @property
    def edge_status(self) -> str | None:
        return self.edge.status if self.edge is not None else None
