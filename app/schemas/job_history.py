from datetime import datetime, UTC

from pydantic import BaseModel

from app.utils.enums import JobStatus, JobType


class JobHistoryBase(BaseModel):
    job_type: JobType
    status: JobStatus | None = None
    progress: int | None = 0
    retry_count: int = 0
    details: str | None = None
    result: str | None = None
    task_id: str | None = None
    user_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    library_id: str | None = None
    # Set when an edge device runs the job instead of the server's worker.
    edge_id: str | None = None
    edge_name: str | None = None


class JobHistoryCreate(BaseModel):
    job_type: JobType

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job_type": "LIBRARY_SCAN",
                },
            ],
        },
    }


class JobHistoryRead(JobHistoryBase):
    id: str

    model_config = {
        "from_attributes": True,
    }


class JobStartRequest(BaseModel):
    job_type: JobType

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "job_type": "INCREMENTAL_SCAN",
                },
            ],
        },
    }
