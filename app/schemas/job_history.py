from datetime import datetime

from pydantic import BaseModel

from app.utils.enums import JobStatus, JobType


class JobHistoryBase(BaseModel):
    job_type: JobType
    status: JobStatus | None = None
    progress: int | None = 0
    details: str | None = None
    result: str | None = None
    task_id: str | None = None
    user_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class JobHistoryCreate(BaseModel):
    job_type: JobType


class JobHistoryRead(JobHistoryBase):
    id: str

    model_config = {
        "from_attributes": True,
    }


class JobStartRequest(BaseModel):
    job_type: JobType
