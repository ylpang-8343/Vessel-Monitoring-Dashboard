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


def _cookie_attributes(set_cookie_header: str) -> dict[str, str]:
    """Parse a raw `Set-Cookie` value into a lower-cased {attribute: value} map, with valueless
    flags (HttpOnly/Secure) mapped to "". Only the attributes matter here, not the token itself."""
    attrs: dict[str, str] = {}
    for part in set_cookie_header.split(";")[1:]:  # [0] is the cookie name=value pair itself
        name, _, value = part.strip().partition("=")
        attrs[name.lower()] = value
    return attrs


def test_logout_clears_the_cookie_with_the_same_attributes_it_was_set_with(monkeypatch):
    """Regression test for a bug that only ever showed up on a real deployment: logout()'s
    `delete_cookie` used Starlette's defaults (SameSite=Lax, no Secure, no HttpOnly) instead of
    repeating the attributes the cookie was *set* with (SameSite=None, Secure, HttpOnly).

    A browser only removes a cookie when the clearing Set-Cookie matches, and it rejects a
    cross-site response carrying SameSite=Lax outright - so on a deployment with the frontend
    and backend on different domains, pressing "Log out" left the session cookie in place and
    the user stayed signed in (visiting e.g. /map by URL went straight in). It passed locally
    and in `test_logout_clears_session` above because :3000 -> :8000 is same-site and because
    httpx's cookie jar isn't a browser - it honours the deletion either way. Hence this test
    asserts on the raw header instead of on observable client behaviour.
    """
    # A real HTTPS deployment sets this; with it False, `secure` is legitimately absent from
    # both headers and the mismatch this guards against wouldn't be visible.
    monkeypatch.setattr("app.config.settings.cookie_secure", True)

    _register(email="cookie.attrs@example.com", password="Passw0rd!")
    fresh_client = TestClient(app)
    login_resp = fresh_client.post(
        "/api/auth/login", json={"email": "cookie.attrs@example.com", "password": "Passw0rd!"}
    )
    logout_resp = fresh_client.post("/api/auth/logout")

    set_attrs = _cookie_attributes(login_resp.headers["set-cookie"])
    clear_attrs = _cookie_attributes(logout_resp.headers["set-cookie"])

    for attribute in ("samesite", "path", "secure", "httponly"):
        assert attribute in set_attrs, f"login response should set {attribute}"
        assert clear_attrs.get(attribute) == set_attrs.get(attribute), (
            f"logout's Set-Cookie must repeat {attribute!r} exactly as login set it, or browsers "
            f"will ignore the deletion cross-site (set={set_attrs.get(attribute)!r}, "
            f"clear={clear_attrs.get(attribute)!r})"
        )

    # And the deletion must actually be an expiry, not just a matching-attributes no-op.
    assert clear_attrs.get("max-age") == "0"


def test_protected_route_rejects_unauthenticated_request():
    fresh_client = TestClient(app)
    resp = fresh_client.get("/api/vessels")
    assert resp.status_code == 401


def test_authenticated_user_can_reach_vessels(client):
    resp = client.get("/api/vessels")
    assert resp.status_code == 200
