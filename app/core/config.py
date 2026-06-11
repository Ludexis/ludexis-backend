from pathlib import Path
from typing import List

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    )
    PROJECT_NAME: str = "Ludexis Backend"
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    TWITCH_CLIENT_ID: str = ""
    TWITCH_CLIENT_SECRET: str = ""

    IGDB_TOKEN_URL: str = "https://id.twitch.tv/oauth2/token"
    IGDB_API_URL: str = "https://api.igdb.com/v4"

    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn
    CELERY_BROKER_URL: RedisDsn
    CELERY_RESULT_BACKEND: RedisDsn
    LIBRARY_SCAN_PATH: str = "./library"
    ARTWORK_STORAGE_PATH: str = "./artwork"
    MAX_ARTWORK_SIZE_MB: int = 10
    ALLOWED_ARTWORK_MIME_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/svg+xml",
    ]

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JOB_MAX_RETRIES: int = 5
    JOB_RETRY_BACKOFF_MAX: int = 300

    CORS_ORIGINS: List[str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()