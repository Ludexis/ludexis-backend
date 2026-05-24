from pydantic import BaseModel


class TagBase(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None


class TagCreate(TagBase):
    pass


class TagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None


class TagRead(TagBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
