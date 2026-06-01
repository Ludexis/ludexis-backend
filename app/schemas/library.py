from pydantic import BaseModel

from app.schemas.base import TimestampedModel


class LibraryBase(BaseModel):
    name: str
    path: str
    enabled: bool = True


class LibraryCreate(LibraryBase):
    pass


class LibraryUpdate(BaseModel):
    name: str | None = None
    path: str | None = None
    enabled: bool | None = None


class LibraryRead(LibraryBase, TimestampedModel):
    id: str

    model_config = {
        "from_attributes": True,
    }