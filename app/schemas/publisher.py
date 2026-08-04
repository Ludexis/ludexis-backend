from pydantic import BaseModel


class PublisherBase(BaseModel):
    name: str
    description: str | None = None
    website: str | None = None


class PublisherCreate(PublisherBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Orbit Publishing",
                    "description": "Specializes in indie releases.",
                    "website": "https://orbit.example",
                },
            ],
        },
    }


class PublisherUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    website: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated publisher profile.",
                    "website": "https://orbit.example/press",
                },
            ],
        },
    }


class PublisherRead(PublisherBase):
    id: str
    entry_count: int = 0

    model_config = {
        "from_attributes": True,
    }
