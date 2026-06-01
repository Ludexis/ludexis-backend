from pydantic import BaseModel


class FranchiseBase(BaseModel):
    name: str
    description: str | None = None
    banner_path: str | None = None
    parent_id: str | None = None


class FranchiseCreate(FranchiseBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Skybound Saga",
                    "description": "Multi-title fantasy franchise.",
                    "banner_path": "D:/Artwork/skybound-banner.png",
                },
            ],
        },
    }


class FranchiseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    banner_path: str | None = None
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


class FranchiseRead(FranchiseBase):
    id: str
    child_ids: list[str] = []

    model_config = {
        "from_attributes": True,
    }
