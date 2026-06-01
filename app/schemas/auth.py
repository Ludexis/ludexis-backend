from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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
    refresh_token: str

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
    refresh_token: str

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
