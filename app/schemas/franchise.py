from pydantic import BaseModel


class FranchiseBase(BaseModel):
    name: str
    description: str | None = None
    banner_path: str | None = None
    parent_id: str | None = None


class FranchiseCreate(FranchiseBase):
    pass


class FranchiseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    banner_path: str | None = None
    parent_id: str | None = None


class FranchiseRead(FranchiseBase):
    id: str
    child_ids: list[str] = []

    model_config = {
        "from_attributes": True,
    }
