from pydantic import BaseModel

class DuplicateArchiveEntry(BaseModel):
    id: str
    title: str
    file_path: str

class DuplicateGroup(BaseModel):
    file_hash: str
    count: int
    entries: list[DuplicateArchiveEntry]