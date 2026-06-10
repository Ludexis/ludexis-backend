from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get(
        "/api/health"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_database_health():
    response = client.get(
        "/api/health/db"
    )

    assert response.status_code == 200
    assert response.json()["database"] == "healthy"


def test_redis_health():
    response = client.get(
        "/api/health/redis"
    )

    assert response.status_code == 200
    assert response.json()["redis"] == "healthy"