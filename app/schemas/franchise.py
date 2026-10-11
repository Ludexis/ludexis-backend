from pydantic import BaseModel


class FranchiseBase(BaseModel):
    name: str
    description: str | None = None
    parent_id: str | None = None


class FranchiseCreate(FranchiseBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Skybound Saga",
                    "description": "Multi-title fantasy franchise.",
                },
            ],
        },
    }


class FranchiseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parent_id: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated franchise overview.",
                    "parent_id": "franchise-uuid-parent",
                },
            ],
        },
    }


class FranchiseImageSource(BaseModel):
    source: str


class FranchiseRead(FranchiseBase):
    id: str
    # banner_path is the image chosen for the franchise; image_path is what to show, falling back to a game's banner.
    banner_path: str | None = None
    image_path: str | None = None
    child_ids: list[str] = []
    entry_count: int = 0

    model_config = {
        "from_attributes": True,
    }
