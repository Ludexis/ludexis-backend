from pydantic import BaseModel

from app.schemas.base import TimestampedModel


class CollectionBase(BaseModel):
    name: str
    description: str | None = None
    cover_path: str | None = None
    banner_path: str | None = None
    visibility: str = "public"


class CollectionCreate(CollectionBase):
    entry_ids: list[str] = []


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_path: str | None = None
    banner_path: str | None = None
    visibility: str | None = None
    entry_ids: list[str] | None = None


class CollectionEntryRequest(BaseModel):
    entry_id: str


class CollectionRead(CollectionBase, TimestampedModel):
    id: str
    entry_ids: list[str] = []

    model_config = {
        "from_attributes": True,
    }
