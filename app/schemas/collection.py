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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Favorites",
                    "description": "Personal favorites for quick access.",
                    "visibility": "public",
                    "entry_ids": ["entry-uuid-1", "entry-uuid-2"],
                },
            ],
        },
    }


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_path: str | None = None
    banner_path: str | None = None
    visibility: str | None = None
    entry_ids: list[str] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated description.",
                    "visibility": "private",
                    "entry_ids": ["entry-uuid-3"],
                },
            ],
        },
    }


class CollectionEntryRequest(BaseModel):
    entry_id: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "entry_id": "entry-uuid-1",
                },
            ],
        },
    }


class CollectionRead(CollectionBase, TimestampedModel):
    id: str
    entry_ids: list[str] = []

    model_config = {
        "from_attributes": True,
    }
