from pydantic import BaseModel


class PermissionBase(BaseModel):
    name: str
    description: str | None = None


class PermissionCreate(PermissionBase):
    pass


class PermissionRead(PermissionBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
