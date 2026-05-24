from pathlib import Path
from typing import List

from pydantic import BaseSettings, PostgresDsn, RedisDsn, field_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "Ludexis Backend"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    DATABASE_URL: PostgresDsn = "postgresql+psycopg://ludexis:ludexis@db:5432/ludexis"
    REDIS_URL: RedisDsn = "redis://redis:6379/0"
    CELERY_BROKER_URL: RedisDsn = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: RedisDsn = "redis://redis:6379/0"
    LIBRARY_SCAN_PATH: str = "./library"

    JWT_SECRET_KEY: str = "supersecretjwtkey"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    CORS_ORIGINS: List[str] = ["*"]

    class Config:
        env_file = Path(__file__).resolve().parents[1] / ".env"
        env_file_encoding = "utf-8"

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
