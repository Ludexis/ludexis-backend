from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_ci_database_has_admin():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin123!",
        },
    )

    assert response.status_code == 200