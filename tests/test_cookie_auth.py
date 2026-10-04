from fastapi.testclient import TestClient

from main import app

client = TestClient(app)
CSRF = {"X-Requested-With": "ludexis"}


def login(username="admin", password="Admin123!"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_login_sets_httponly_session_cookies():
    response = login()
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith("ludexis_access="))
    refresh = next(c for c in cookies if c.startswith("ludexis_refresh="))
    assert "HttpOnly" in access and "SameSite=lax" in access and "Path=/" in access
    assert "HttpOnly" in refresh and "Path=/api/auth" in refresh
    assert response.json()["expires_in"] > 0


def test_cookie_authenticates_reads_and_writes_need_the_csrf_header():
    token = login().json()["access_token"]
    cookie = {"Cookie": f"ludexis_access={token}"}

    assert client.get("/api/auth/me", headers=cookie).json()["username"] == "admin"
    assert client.post("/api/tags/", json={"name": "csrf-check"}, headers=cookie).status_code == 403

    created = client.post("/api/tags/", json={"name": f"csrf-ok-{token[-8:]}"}, headers={**cookie, **CSRF})
    assert created.status_code == 201
    # The Authorization header needs no CSRF header.
    assert client.delete(f"/api/tags/{created.json()['id']}", headers={"Authorization": f"Bearer {token}"}).status_code == 204


def test_cookie_refresh_rotates_without_exposing_tokens():
    refresh_token = login().json()["refresh_token"]
    cookie = {"Cookie": f"ludexis_refresh={refresh_token}"}

    assert client.post("/api/auth/refresh", headers=cookie).status_code == 403
    response = client.post("/api/auth/refresh", headers={**cookie, **CSRF})
    assert response.status_code == 200
    assert response.json()["access_token"] is None
    assert any(c.startswith("ludexis_access=") for c in response.headers.get_list("set-cookie"))
    # The old refresh token was rotated out.
    assert client.post("/api/auth/refresh", headers={**cookie, **CSRF}).status_code == 401


def test_logout_revokes_the_cookie_refresh_token_and_clears_cookies():
    refresh_token = login().json()["refresh_token"]
    cookie = {"Cookie": f"ludexis_refresh={refresh_token}"}

    response = client.post("/api/auth/logout", headers={**cookie, **CSRF})
    assert response.status_code == 204
    assert any(c.startswith('ludexis_access=""') or "Max-Age=0" in c for c in response.headers.get_list("set-cookie"))
    assert client.post("/api/auth/refresh", json={"refresh_token": refresh_token}).status_code == 401


def test_repeated_failures_are_rate_limited():
    for _ in range(5):
        assert login(password="wrong-password").status_code == 401
    blocked = login(password="wrong-password")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    # Even the right password waits out the window.
    assert login().status_code == 429


def test_success_clears_earlier_failures():
    for _ in range(4):
        login(password="wrong-password")
    assert login().status_code == 200
    for _ in range(4):
        assert login(password="wrong-password").status_code == 401
    assert login().status_code == 200
