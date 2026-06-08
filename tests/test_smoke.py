from app.core.config import settings


def test_config_loads():
    assert settings is not None