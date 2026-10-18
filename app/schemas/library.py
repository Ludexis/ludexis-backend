from datetime import datetime
from pydantic import BaseModel

from app.schemas.base import TimestampedModel


class LibraryBase(BaseModel):
    name: str
    path: str
    enabled: bool = True
    # Empty: on the server. Otherwise the edge device whose drive holds it, as that machine names the path.
    edge_id: str | None = None


class LibraryCreate(LibraryBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Main Library",
                    "path": "D:/GameArchives",
                    "enabled": True,
                },
            ],
        },
    }


class LibraryUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    enabled: bool | None = None
    # Sent as null, the library moves to the server; left out, it stays where it is.
    edge_id: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Legacy Library",
                    "enabled": False,
                },
            ],
        },
    }


class LibraryRead(LibraryBase, TimestampedModel):
    id: str
    status: str = "ONLINE"
    last_seen_at: datetime | None = None
    last_scan_at: datetime | None = None
    last_error: str | None = None
    edge_name: str | None = None
    edge_status: str | None = None
    drive_id: str | None = None
    drive_mount: str | None = None
    pending_changes: int = 0

    model_config = {
        "from_attributes": True,
    }