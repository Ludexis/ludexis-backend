from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    # Omitted when the browser refreshes through its cookie, so page scripts never see the tokens.
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int


class TokenPayload(BaseModel):
    sub: str
    type: str


class LoginRequest(BaseModel):
    username: str
    password: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "username": "admin",
                    "password": "P@ssw0rd!",
                },
            ],
        },
    }


class RefreshRequest(BaseModel):
    # Optional: the browser sends its refresh cookie instead.
    refresh_token: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                },
            ],
        },
    }


class LogoutRequest(BaseModel):
    refresh_token: str | None = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                },
            ],
        },
    }


class PasswordResetRequest(BaseModel):
    password: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "password": "NewP@ssw0rd!",
                },
            ],
        },
    }
