from pydantic import BaseModel

from app.schemas.permission import PermissionRead


class RoleBase(BaseModel):
    name: str
    description: str | None = None


class RoleCreate(RoleBase):
    permission_ids: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    permission_ids: list[str] | None = None


class RoleRead(RoleBase):
    id: str
    permissions: list[PermissionRead] = []

    model_config = {
        "from_attributes": True,
    }
