from fastapi.testclient import TestClient
from main import app

from app.providers.notices import clear_notice, set_notice

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


def test_notices_list_only_providers_the_account_may_use():
    set_notice("IGDB", "Rate limit reached", 900)
    set_notice("VNDB", "Signed out", 900)
    set_notice("Nowhere", "Not an enabled provider", 900)

    admin = client.get("/api/metadata/notices", headers=auth_header(login(ADMIN_USERNAME, ADMIN_PASSWORD)))
    user = client.get("/api/metadata/notices", headers=auth_header(login(USER_USERNAME, USER_PASSWORD)))

    assert [(notice["provider"], notice["message"]) for notice in admin.json()] == [("VNDB", "Signed out"), ("IGDB", "Rate limit reached")]
    assert admin.json()[0]["expires_at"] is not None
    # Restricted providers stay hidden from accounts not allowed them.
    assert [notice["provider"] for notice in user.json()] == ["IGDB"]

    clear_notice("IGDB")
    clear_notice("VNDB")
    assert client.get("/api/metadata/notices", headers=auth_header(login(ADMIN_USERNAME, ADMIN_PASSWORD))).json() == []
