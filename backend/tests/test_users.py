from app.db import SessionLocal
from app.models import User, UserRole


def _register_regular_user(email="member@example.com"):
    # Deliberately NOT using admin_client here: registering through it would overwrite its
    # session cookie with the new user's session, silently logging the admin out mid-test.
    from fastapi.testclient import TestClient

    from app.main import app

    resp = TestClient(app).post(
        "/api/auth/register",
        json={"email": email, "password": "Passw0rd!", "confirm_password": "Passw0rd!"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_admin_can_list_users(admin_client):
    resp = admin_client.get("/api/users")
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert "test.admin@example.com" in emails


def test_non_admin_cannot_list_users(client):
    resp = client.get("/api/users")
    assert resp.status_code == 403


def test_admin_can_promote_user(admin_client):
    user_id = _register_regular_user()
    resp = admin_client.patch(f"/api/users/{user_id}/role", json={"role": "admin"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_admin_can_demote_admin_when_another_admin_exists(admin_client):
    user_id = _register_regular_user()
    admin_client.patch(f"/api/users/{user_id}/role", json={"role": "admin"})

    resp = admin_client.patch(f"/api/users/{user_id}/role", json={"role": "user"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "user"


def test_cannot_demote_the_last_remaining_admin(admin_client):
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == "test.admin@example.com").first()
        admin_id = admin.id
        assert db.query(User).filter(User.role == UserRole.ADMIN).count() == 1
    finally:
        db.close()

    resp = admin_client.patch(f"/api/users/{admin_id}/role", json={"role": "user"})
    assert resp.status_code == 409


def test_update_role_unknown_user_404(admin_client):
    resp = admin_client.patch("/api/users/999999/role", json={"role": "admin"})
    assert resp.status_code == 404
