from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.utils.enums import JobStatus, JobType

EdgeOS = Literal["linux", "windows"]


class EdgeDrive(BaseModel):
    # Filesystem UUID (Linux) or volume serial (Windows).
    id: str
    mount: str
    label: str | None = None
    total: int | None = None
    free: int | None = None


class EdgeDeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)

    model_config = {"json_schema_extra": {"examples": [{"name": "Laptop"}]}}


class EdgeDeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    autoscan: bool | None = None


class EdgeLibrarySummary(BaseModel):
    id: str
    name: str
    path: str
    status: str
    # Learnt at its first scan; groups the library under its drive.
    drive_id: str | None = None
    drive_mount: str | None = None

    model_config = {"from_attributes": True}


class EdgeDeviceRead(BaseModel):
    id: str
    name: str
    status: Literal["PENDING", "ONLINE", "OFFLINE"]
    autoscan: bool
    last_seen_at: datetime | None = None
    version: str | None = None
    # The device runs another major.minor release than the server.
    update_available: bool = False
    hostname: str | None = None
    os: EdgeOS | None = None
    drives: list[EdgeDrive] = []
    libraries: list[EdgeLibrarySummary] = []
    created_at: datetime


class EdgeDeviceCreated(EdgeDeviceRead):
    # Shown once; only its hash is kept.
    token: str


class EdgeBundleRequest(BaseModel):
    os: EdgeOS
    # The bundle carries the token, so it is only built for someone who holds it.
    token: str


class EdgePoll(BaseModel):
    version: str
    hostname: str | None = None
    os: EdgeOS
    drives: list[EdgeDrive] = []


class EdgeLibrary(BaseModel):
    id: str
    name: str
    path: str
    enabled: bool
    status: str
    drive_id: str | None = None
    drive_subpath: str | None = None

    model_config = {"from_attributes": True}


class EdgeJob(BaseModel):
    id: str
    job_type: JobType
    status: JobStatus
    library_id: str | None = None
    # Empty for automatic scans (a drive connected, a schedule), which only count new files instead of hashing them.
    user_id: str | None = None

    model_config = {"from_attributes": True}


class EdgePollResponse(BaseModel):
    poll_seconds: int
    server_version: str
    autoscan: bool
    libraries: list[EdgeLibrary]
    jobs: list[EdgeJob]


class EdgeLibraryState(BaseModel):
    # relative_path -> [file_size, modified_time ISO, has_hash]
    entries: dict[str, list]


class EdgeProgress(BaseModel):
    done: int
    total: int
    details: str | None = None


class EdgeProgressResponse(BaseModel):
    cancelled: bool


class EdgeFailure(BaseModel):
    error: str = Field(max_length=2000)
