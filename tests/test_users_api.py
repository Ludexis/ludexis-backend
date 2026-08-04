from uuid import uuid4

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def admin_token():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "admin",
            "password": "Admin123!",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def user_token():
    response = client.post(
        "/api/auth/login",
        json={
            "username": "testuser",
            "password": "Test123!",
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def admin_headers():
    return {"Authorization": f"Bearer {admin_token()}"}


def create_user_payload(username=None, email=None, password="P@ssw0rd!123"):
    return {
        "username": username or f"user_{uuid4().hex}",
        "email": email or f"{uuid4().hex}@example.com",
        "password": password,
    }


def test_create_user_returns_user_read():
    data = create_user_payload()
    response = client.post("/api/users/", json=data, headers=admin_headers())
    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["username"] == data["username"]
    assert body["email"] == data["email"]
    assert body["is_active"] is True
    assert body["is_superuser"] is False


def test_create_user_duplicate_username_returns_400():
    data = create_user_payload()
    first = client.post("/api/users/", json=data, headers=admin_headers())
    assert first.status_code == 201
    duplicate = client.post(
        "/api/users/",
        json={**data, "email": f"{uuid4().hex}@example.com"},
        headers=admin_headers(),
    )
    assert duplicate.status_code == 400


def test_create_user_duplicate_email_returns_400():
    data = create_user_payload()
    first = client.post("/api/users/", json=data, headers=admin_headers())
    assert first.status_code == 201
    duplicate = client.post(
        "/api/users/",
        json={**data, "username": f"user_{uuid4().hex}"},
        headers=admin_headers(),
    )
    assert duplicate.status_code == 400


def test_list_users_contains_created_user():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    response = client.get("/api/users/", headers=admin_headers())
    assert response.status_code == 200
    assert any(user["id"] == user_id for user in response.json())


def test_get_user_by_id():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    response = client.get(f"/api/users/{user_id}", headers=admin_headers())
    assert response.status_code == 200
    assert response.json()["id"] == user_id
    assert response.json()["username"] == data["username"]


def test_get_nonexistent_user_returns_404():
    response = client.get(f"/api/users/{uuid4()}", headers=admin_headers())
    assert response.status_code == 404


def test_patch_user_updates_email():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    new_email = f"{uuid4().hex}@example.com"
    response = client.patch(
        f"/api/users/{user_id}",
        json={"email": new_email},
        headers=admin_headers(),
    )
    assert response.status_code == 200
    assert response.json()["email"] == new_email


def test_deactivate_user():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    response = client.post(
        f"/api/users/{user_id}/deactivate", headers=admin_headers()
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_activate_user():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    deactivated = client.post(
        f"/api/users/{user_id}/deactivate", headers=admin_headers()
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    activated = client.post(
        f"/api/users/{user_id}/activate", headers=admin_headers()
    )
    assert activated.status_code == 200
    assert activated.json()["is_active"] is True


def test_reset_password_allows_login():
    username = f"user_{uuid4().hex}"
    data = create_user_payload(username=username)
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    new_password = "NewP@ssw0rd!456"
    reset = client.post(
        f"/api/users/{user_id}/reset-password",
        json={"password": new_password},
        headers=admin_headers(),
    )
    assert reset.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": new_password,
        },
    )
    assert login.status_code == 200
    assert "access_token" in login.json()


def test_delete_user_soft_deletes():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    response = client.delete(f"/api/users/{user_id}", headers=admin_headers())
    assert response.status_code == 204

    after = client.get(f"/api/users/{user_id}", headers=admin_headers())
    assert after.status_code == 404


def test_list_users_requires_admin():
    response = client.get("/api/users/", headers={"Authorization": f"Bearer {user_token()}"})
    assert response.status_code == 403


def test_create_user_requires_admin():
    response = client.post(
        "/api/users/",
        json=create_user_payload(),
        headers={"Authorization": f"Bearer {user_token()}"},
    )
    assert response.status_code == 403


def test_patch_user_requires_admin():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    response = client.patch(
        f"/api/users/{user_id}",
        json={"email": f"{uuid4().hex}@example.com"},
        headers={"Authorization": f"Bearer {user_token()}"},
    )
    assert response.status_code == 403


def test_delete_user_requires_admin():
    data = create_user_payload()
    created = client.post("/api/users/", json=data, headers=admin_headers())
    assert created.status_code == 201
    user_id = created.json()["id"]

    response = client.delete(
        f"/api/users/{user_id}",
        headers={"Authorization": f"Bearer {user_token()}"},
    )
    assert response.status_code == 403


def test_list_users_requires_auth():
    response = client.get("/api/users/")
    assert response.status_code == 401
