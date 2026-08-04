from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin123!"
USER_USERNAME = "testuser"
USER_PASSWORD = "Test123!"


def login(username, password):
    response = client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_header(token):
    return {
        "Authorization": f"Bearer {token}",
    }


def test_search_requires_auth():
    response = client.get(
        "/api/metadata/search",
    )
    assert response.status_code == 401


def test_search_requires_q():
    token = login(
        ADMIN_USERNAME,
        ADMIN_PASSWORD,
    )
    response = client.get(
        "/api/metadata/search",
        headers=auth_header(token),
    )
    assert response.status_code == 422


def test_details_unknown_provider_404_admin():
    token = login(
        ADMIN_USERNAME,
        ADMIN_PASSWORD,
    )
    response = client.get(
        "/api/metadata/details/nosuchprovider/xyz",
        headers=auth_header(token),
    )
    assert response.status_code == 404


def test_details_requires_auth():
    response = client.get(
        "/api/metadata/details/nosuchprovider/xyz",
    )
    assert response.status_code == 401


def test_artwork_unknown_provider_404_admin():
    token = login(
        ADMIN_USERNAME,
        ADMIN_PASSWORD,
    )
    response = client.get(
        "/api/metadata/artwork/nosuchprovider/xyz",
        headers=auth_header(token),
    )
    assert response.status_code == 404


def test_artwork_requires_auth():
    response = client.get(
        "/api/metadata/artwork/nosuchprovider/xyz",
    )
    assert response.status_code == 401


def test_details_unknown_provider_404_user():
    token = login(
        USER_USERNAME,
        USER_PASSWORD,
    )
    response = client.get(
        "/api/metadata/details/nosuchprovider/xyz",
        headers=auth_header(token),
    )
    assert response.status_code == 404
