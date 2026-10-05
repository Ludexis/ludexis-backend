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
