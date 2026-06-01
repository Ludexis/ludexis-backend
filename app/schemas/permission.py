from pydantic import BaseModel


class PermissionBase(BaseModel):
    name: str
    description: str | None = None


class PermissionCreate(PermissionBase):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "ACCESS_ADMIN",
                    "description": "Access administrative endpoints",
                },
            ],
        },
    }


class PermissionRead(PermissionBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
