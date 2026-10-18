import pytest

from app.core.config import Settings


def test_missing_jwt_secret_is_generated_once(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "")
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    first = Settings().JWT_SECRET_KEY
    assert len(first) == 64
    assert Settings().JWT_SECRET_KEY == first
    assert (tmp_path / "jwt_secret").read_text() == first


def test_short_explicit_jwt_secret_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME")
    with pytest.raises(ValueError):
        Settings()


def test_connection_urls_are_built_from_the_postgres_values(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    for name in ("DATABASE_URL", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss/word")
    settings = Settings(_env_file=None)
    assert str(settings.DATABASE_URL) == "postgresql+psycopg://ludexis:p%40ss%2Fword@db:5432/ludexis"
    assert str(settings.CELERY_BROKER_URL) == str(settings.REDIS_URL) == "redis://redis:6379/0"


def test_an_explicit_database_url_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@localhost:5432/x")
    assert str(Settings(_env_file=None).DATABASE_URL) == "postgresql+psycopg://a:b@localhost:5432/x"
