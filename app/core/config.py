import json
import os
import secrets
import time
from pathlib import Path
from typing import List

from pydantic import PostgresDsn, RedisDsn, model_validator
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
    STEAMGRIDDB_API_KEY: str = ""

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
    ]

    # Left empty, a random secret is generated once and kept in CONFIG_DIR, shared by every container.
    JWT_SECRET_KEY: str = ""
    CONFIG_DIR: str = "./config"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JOB_MAX_RETRIES: int = 5
    JOB_RETRY_BACKOFF_MAX: int = 300

    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @model_validator(mode="after")
    def _jwt_secret(self) -> "Settings":
        if not self.JWT_SECRET_KEY:
            self.JWT_SECRET_KEY = _load_or_create_secret(Path(self.CONFIG_DIR) / "jwt_secret")
        # Placeholders such as CHANGE_ME would let anyone forge tokens.
        elif len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters (generate one with: openssl rand -hex 32)")
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        value = self.CORS_ORIGINS.strip()
        if value.startswith("[") and value.endswith("]"):
            try:
                return [origin.strip() for origin in json.loads(value)]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in value.split(",") if origin.strip()]


def _load_or_create_secret(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # O_EXCL: when backend, worker and beat start together, exactly one of them writes the secret.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        for _ in range(50):
            value = path.read_text(encoding="utf-8").strip()
            if len(value) >= 32:
                return value
            time.sleep(0.1)
        raise RuntimeError(f"{path} exists but holds no usable secret; delete it to generate a new one")
    value = secrets.token_hex(32)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(value)
    return value


settings = Settings()