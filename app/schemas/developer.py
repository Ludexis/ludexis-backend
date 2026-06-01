from pydantic import BaseModel


class DeveloperBase(BaseModel):
    name: str
    description: str | None = None
    website: str | None = None


class DeveloperCreate(DeveloperBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Studio Polaris",
                    "description": "Independent game studio.",
                    "website": "https://studiopolaris.example",
                },
            ],
        },
    }


class DeveloperUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    website: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated studio profile.",
                    "website": "https://studiopolaris.example/about",
                },
            ],
        },
    }


class DeveloperRead(DeveloperBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
