import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base

POLL_SECONDS = 15
# Missing three check-ins in a row counts as offline.
ONLINE_WITHIN = timedelta(seconds=POLL_SECONDS * 3)


class EdgeDevice(Base):
    """A machine that scans drives attached to it and sends the results here; the database stays on the server."""

    __tablename__ = "edge_devices"
    __allow_unmapped__ = True

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: str = mapped_column(sa.String(128), nullable=False, unique=True)
    # sha256 of the device token; the token itself is shown once and never stored.
    token_hash: str = mapped_column(sa.String(64), nullable=False, unique=True)
    # Scan a library as soon as its drive shows up on the device.
    autoscan: bool = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())
    last_seen_at = mapped_column(sa.DateTime(timezone=True), nullable=True)
    version: str = mapped_column(sa.String(32), nullable=True)
    hostname: str = mapped_column(sa.String(256), nullable=True)
    os: str = mapped_column(sa.String(16), nullable=True)
    # The drives the device reported at its last check-in: [{id, mount, label, total, free}].
    drives = mapped_column(sa.JSON, nullable=True)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    libraries = relationship("Library", back_populates="edge")

    @property
    def status(self) -> str:
        if self.last_seen_at is None:
            return "PENDING"
        return "ONLINE" if datetime.now(UTC) - self.last_seen_at <= ONLINE_WITHIN else "OFFLINE"
