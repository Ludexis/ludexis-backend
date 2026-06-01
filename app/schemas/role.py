from pydantic import BaseModel

from app.schemas.permission import PermissionRead


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(RoleBase):
    permission_ids: list[str] = []

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Curator",
                    "description": "Curates metadata and collections.",
                    "permission_ids": ["perm-uuid-1", "perm-uuid-2"],
                },
            ],
        },
    }


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_ids: list[str] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Updated role description.",
                    "permission_ids": ["perm-uuid-3"],
                },
            ],
        },
    }


class RoleRead(RoleBase):
    id: str
    permissions: list[PermissionRead] = []

    model_config = {
        "from_attributes": True,
    }
