from pydantic import BaseModel


class PublisherBase(BaseModel):
    name: str
    description: str | None = None
    website: str | None = None


class PublisherCreate(PublisherBase):
    pass


class PublisherUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    website: str | None = None


class PublisherRead(PublisherBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
