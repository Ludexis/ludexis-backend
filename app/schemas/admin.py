from pydantic import BaseModel


class AdminStats(BaseModel):
    archive_entries: int
    collections: int
    tags: int
    developers: int
    publishers: int
    franchises: int
    users: int
    metadata_coverage: float
    verification_coverage: float
