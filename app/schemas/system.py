from datetime import datetime

from pydantic import BaseModel, Field


class ScheduledTaskRead(BaseModel):
    key: str
    name: str
    job_type: str
    enabled: bool
    hour: int
    minute: int
    day_of_week: int | None = None
    last_run_at: datetime | None = None
    last_job_id: str | None = None
    last_job_status: str | None = None
    next_run_at: datetime | None = None


class ScheduledTaskUpdate(BaseModel):
    enabled: bool | None = None
    hour: int | None = Field(None, ge=0, le=23)
    minute: int | None = Field(None, ge=0, le=59)
    # -1 switches a weekly task to daily.
    day_of_week: int | None = Field(None, ge=-1, le=6)


class SettingsRead(BaseModel):
    server_name: str
    provider_order: list[str]
    available_providers: list[str]
    igdb_client_id: str
    igdb_configured: bool
    igdb_from_env: bool
    steamgriddb_configured: bool
    steamgriddb_from_env: bool


class SettingsUpdate(BaseModel):
    server_name: str | None = Field(None, min_length=1, max_length=128)
    provider_order: list[str] | None = None
    igdb_client_id: str | None = None
    # Write-only: never returned by the API.
    igdb_client_secret: str | None = None
    # Write-only: never returned by the API.
    steamgriddb_api_key: str | None = None
