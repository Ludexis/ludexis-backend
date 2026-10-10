from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.role import RoleRead


class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False
    allow_restricted: bool = False
    # Games in these collections are hidden from the user.
    blocked_collection_ids: list[str] = []


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=256)
    role_ids: list[str] = []

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "alex",
                    "email": "alex@example.com",
                    "password": "P@ssw0rd!",
                    "is_active": True,
                    "is_superuser": False,
                    "role_ids": ["role-uuid-1"],
                },
            ],
        },
    }


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=256)
    is_active: bool | None = None
    is_superuser: bool | None = None
    role_ids: list[str] | None = None
    allow_restricted: bool | None = None
    blocked_collection_ids: list[str] | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "alex.new@example.com",
                    "is_active": True,
                    "role_ids": ["role-uuid-2"],
                },
            ],
        },
    }


class UserRead(UserBase):
    id: str
    must_change_password: bool = False
    roles: list[RoleRead] = []
    created_at: datetime | None = None

    model_config = {
        "from_attributes": True,
    }
