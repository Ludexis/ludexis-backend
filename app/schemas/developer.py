from pydantic import BaseModel


class DeveloperBase(BaseModel):
    name: str
    description: str | None = None
    website: str | None = None


class DeveloperCreate(DeveloperBase):
    pass


class DeveloperUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    website: str | None = None


class DeveloperRead(DeveloperBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
