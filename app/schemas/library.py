from pydantic import BaseModel

from app.schemas.base import TimestampedModel


class LibraryBase(BaseModel):
    name: str
    path: str
    enabled: bool = True


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

    model_config = {
        "from_attributes": True,
    }