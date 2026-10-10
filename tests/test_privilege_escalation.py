import uuid

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def login(username, password):
    tokens = client.post("/api/auth/login", json={"username": username, "password": password}).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def make_manager():
    """A non-superuser whose only right is managing users."""
    admin = login("admin", "Admin123!")
    permissions = {p["name"]: p["id"] for p in client.get("/api/permissions/", headers=admin).json()}
    roles = {r["name"]: r["id"] for r in client.get("/api/roles/", headers=admin).json()}
    role = client.post("/api/roles/", headers=admin, json={"name": f"managers-{uuid.uuid4().hex[:6]}", "permission_ids": [permissions["MANAGE_USERS"]]}).json()
    name = f"manager-{uuid.uuid4().hex[:6]}"
    manager = client.post("/api/users/", headers=admin, json={
        "username": name, "email": f"{name}@example.com", "password": "Manager-1", "role_ids": [role["id"]],
    }).json()
    return admin, login(name, "Manager-1"), manager, permissions, roles, role


def test_managing_users_does_not_reach_above_oneself():
    admin, headers, manager, permissions, roles, own_role = make_manager()
    admin_id = client.get("/api/auth/me", headers=admin).json()["id"]

    def new_user(**extra):
        name = f"u-{uuid.uuid4().hex[:6]}"
        return client.post("/api/users/", headers=headers, json={"username": name, "email": f"{name}@example.com", "password": "Passw0rd!", **extra})

    # Roles carrying rights the manager lacks can be neither made, changed, removed nor handed out.
    assert client.post("/api/roles/", headers=headers, json={"name": "sneaky", "permission_ids": [permissions["ACCESS_ADMIN"]]}).status_code == 403
    assert client.patch(f"/api/roles/{roles['Administrator']}", headers=headers, json={"name": "renamed"}).status_code == 403
    assert client.delete(f"/api/roles/{roles['Administrator']}", headers=headers).status_code == 403
    assert new_user(role_ids=[roles["Administrator"]]).status_code == 403
    assert new_user(allow_restricted=True).status_code == 403
    # Superusers and one's own access are out of reach.
    assert client.patch(f"/api/users/{admin_id}", headers=headers, json={"email": "x@example.com"}).status_code == 403
    assert client.post(f"/api/users/{admin_id}/deactivate", headers=headers).status_code == 403
    assert client.patch(f"/api/users/{manager['id']}", headers=headers, json={"blocked_collection_ids": []}).status_code == 403

    # Within their own rights they still work.
    assert new_user(role_ids=[own_role["id"]]).status_code == 201
