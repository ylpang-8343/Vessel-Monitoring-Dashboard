from fastapi.testclient import TestClient

from app.main import app

anon = TestClient(app)


def _register(email="new.user@example.com", password="Passw0rd!", confirm=None):
    return anon.post(
        "/api/auth/register",
        json={"email": email, "password": password, "confirm_password": confirm or password},
    )


def test_register_creates_regular_user_never_admin():
    resp = _register()
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new.user@example.com"
    assert body["role"] == "user"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_password_too_short():
    resp = _register(password="Ab1!", confirm="Ab1!")
    assert resp.status_code == 422


def test_register_rejects_password_missing_uppercase():
    resp = _register(password="lowercase1!", confirm="lowercase1!")
    assert resp.status_code == 422


def test_register_rejects_password_missing_lowercase():
    resp = _register(password="UPPERCASE1!", confirm="UPPERCASE1!")
    assert resp.status_code == 422


def test_register_rejects_password_missing_symbol():
    resp = _register(password="Passw0rd", confirm="Passw0rd")
    assert resp.status_code == 422


def test_register_rejects_mismatched_confirmation():
    resp = _register(password="Passw0rd!", confirm="Different1!")
    assert resp.status_code == 422


def test_register_rejects_duplicate_email():
    _register(email="dup@example.com")
    resp = _register(email="dup@example.com")
    assert resp.status_code == 409


def test_login_success_sets_session_cookie():
    _register(email="login.test@example.com", password="Passw0rd!")
    fresh_client = TestClient(app)
    resp = fresh_client.post("/api/auth/login", json={"email": "login.test@example.com", "password": "Passw0rd!"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "login.test@example.com"

    me = fresh_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "login.test@example.com"


def test_login_wrong_password_rejected():
    _register(email="wrongpw@example.com", password="Passw0rd!")
    fresh_client = TestClient(app)
    resp = fresh_client.post("/api/auth/login", json={"email": "wrongpw@example.com", "password": "NotThePass1!"})
    assert resp.status_code == 401


def test_login_unknown_email_rejected():
    fresh_client = TestClient(app)
    resp = fresh_client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Passw0rd!"})
    assert resp.status_code == 401


def test_me_without_session_rejected():
    fresh_client = TestClient(app)
    resp = fresh_client.get("/api/auth/me")
    assert resp.status_code == 401


def test_logout_clears_session():
    _register(email="logout.test@example.com", password="Passw0rd!")
    fresh_client = TestClient(app)
    fresh_client.post("/api/auth/login", json={"email": "logout.test@example.com", "password": "Passw0rd!"})
    assert fresh_client.get("/api/auth/me").status_code == 200

    logout_resp = fresh_client.post("/api/auth/logout")
    assert logout_resp.status_code == 204
    assert fresh_client.get("/api/auth/me").status_code == 401


def test_protected_route_rejects_unauthenticated_request():
    fresh_client = TestClient(app)
    resp = fresh_client.get("/api/vessels")
    assert resp.status_code == 401


def test_authenticated_user_can_reach_vessels(client):
    resp = client.get("/api/vessels")
    assert resp.status_code == 200
