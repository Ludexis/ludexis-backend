from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    username: str
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False


class UserCreate(UserBase):
    password: str
    role_ids: list[str] = []


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    password: str | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    role_ids: list[str] | None = None


class UserRead(UserBase):
    id: str

    model_config = {
        "from_attributes": True,
    }
