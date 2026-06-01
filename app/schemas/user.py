from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: str
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
    password: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    role_ids: list[str] | None = None

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

    model_config = {
        "from_attributes": True,
    }
