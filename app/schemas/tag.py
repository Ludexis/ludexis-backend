from pydantic import BaseModel


class TagBase(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None


class TagCreate(TagBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "retro",
                    "description": "Classic era titles.",
                    "color": "#FF9900",
                },
            ],
        },
    }


class TagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated tag description.",
                    "color": "#FF8800",
                },
            ],
        },
    }


class TagRead(TagBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
