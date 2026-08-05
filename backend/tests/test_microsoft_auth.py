from urllib.parse import parse_qs, urlparse

import pytest

FAKE_PROFILE = {"mail": "ms.user@example.com", "id": "fake-oid-123", "displayName": "MS User"}


def _configure(monkeypatch):
    monkeypatch.setattr("app.config.settings.microsoft_client_id", "test-client-id")
    monkeypatch.setattr("app.config.settings.microsoft_client_secret", "test-client-secret")


def _anon_client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)


def test_status_reports_unconfigured_by_default():
    resp = _anon_client().get("/api/auth/microsoft/status")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False}


def test_status_reports_configured_once_credentials_are_set(monkeypatch):
    _configure(monkeypatch)
    resp = _anon_client().get("/api/auth/microsoft/status")
    assert resp.json() == {"configured": True}


def test_login_503_when_not_configured():
    resp = _anon_client().get("/api/auth/microsoft/login", follow_redirects=False)
    assert resp.status_code == 503


def test_login_redirects_to_microsoft_with_state_cookie(monkeypatch):
    _configure(monkeypatch)
    client = _anon_client()
    resp = client.get("/api/auth/microsoft/login", follow_redirects=False)
    assert resp.status_code == 307

    location = resp.headers["location"]
    assert location.startswith("https://login.microsoftonline.com/common/oauth2/v2.0/authorize?")
    query = parse_qs(urlparse(location).query)
    assert query["client_id"] == ["test-client-id"]
    assert query["response_type"] == ["code"]
    assert "state" in query

    assert "ms_oauth_state" in resp.cookies
    assert resp.cookies["ms_oauth_state"] == query["state"][0]


def test_callback_missing_state_redirects_to_login_with_error():
    resp = _anon_client().get("/api/auth/microsoft/callback?code=abc", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("http://localhost:3000/login?error=")


def test_callback_state_mismatch_redirects_to_login_with_error(monkeypatch):
    _configure(monkeypatch)
    client = _anon_client()
    client.get("/api/auth/microsoft/login", follow_redirects=False)  # sets a real state cookie

    resp = client.get("/api/auth/microsoft/callback?code=abc&state=not-the-real-state", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("http://localhost:3000/login?error=")
    assert "session_token" not in resp.cookies


def test_callback_provider_error_param_redirects_with_error():
    resp = _anon_client().get("/api/auth/microsoft/callback?error=access_denied", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("http://localhost:3000/login?error=")


def _complete_login(client, monkeypatch, profile=FAKE_PROFILE):
    """Drive the full authorize -> (fake) Microsoft -> callback round trip against a TestClient,
    mocking only the two outbound HTTP calls this app makes to Microsoft - the state/cookie/
    redirect plumbing in between is exercised for real."""
    monkeypatch.setattr(
        "app.services.microsoft_auth_service.exchange_code_for_token", lambda code: "fake-access-token"
    )
    monkeypatch.setattr("app.services.microsoft_auth_service.fetch_profile", lambda token: profile)

    login_resp = client.get("/api/auth/microsoft/login", follow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]
    return client.get(f"/api/auth/microsoft/callback?code=fake-code&state={state}", follow_redirects=False)


def test_callback_creates_a_new_user_role_user_and_logs_in(monkeypatch):
    _configure(monkeypatch)
    client = _anon_client()

    resp = _complete_login(client, monkeypatch)
    assert resp.status_code == 307
    assert resp.headers["location"] == "http://localhost:3000"
    assert "session_token" in resp.cookies

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "ms.user@example.com"
    assert body["role"] == "user"  # never admin, same rule as password registration
    assert body["auth_provider"] == "microsoft"
    assert body["microsoft_linked"] is True


def test_local_login_rejected_for_a_microsoft_only_account(monkeypatch):
    _configure(monkeypatch)
    client = _anon_client()
    _complete_login(client, monkeypatch)

    # A fresh, unauthenticated client (the Microsoft flow above left `client` logged in) tries
    # the ordinary password form against that same email - must fail cleanly, not 500.
    from fastapi.testclient import TestClient

    from app.main import app

    anon = TestClient(app)
    resp = anon.post("/api/auth/login", json={"email": "ms.user@example.com", "password": "Whatever123!"})
    assert resp.status_code == 401


def test_callback_links_to_an_existing_local_account_by_email(client, monkeypatch, db_session):
    # `client` fixture already registered test.user@example.com with a password.
    _configure(monkeypatch)

    from app.models import User

    existing = db_session.query(User).filter(User.email == "test.user@example.com").first()
    assert existing.auth_provider.value == "local"
    assert existing.microsoft_id is None
    assert existing.microsoft_linked is False
    existing_id = existing.id

    ms_client_profile = {"mail": "test.user@example.com", "id": "linked-oid-456"}
    anon_for_oauth = _anon_client()
    resp = _complete_login(anon_for_oauth, monkeypatch, profile=ms_client_profile)
    assert resp.status_code == 307

    me = anon_for_oauth.get("/api/auth/me").json()
    assert me["id"] == existing_id  # same account, not a duplicate
    # The badge shown in Settings -> Users is driven by this flag, not auth_provider - a
    # linked account must show it even though it didn't originally sign *up* via Microsoft.
    assert me["auth_provider"] == "local"
    assert me["microsoft_linked"] is True

    db_session.refresh(existing)
    assert existing.microsoft_id == "linked-oid-456"
    assert existing.microsoft_linked is True


def test_callback_http_failure_redirects_with_error(monkeypatch):
    import httpx

    _configure(monkeypatch)

    def _boom(code):
        raise httpx.ConnectError("could not reach Microsoft")

    monkeypatch.setattr("app.services.microsoft_auth_service.exchange_code_for_token", _boom)

    client = _anon_client()
    login_resp = client.get("/api/auth/microsoft/login", follow_redirects=False)
    state = parse_qs(urlparse(login_resp.headers["location"]).query)["state"][0]
    resp = client.get(f"/api/auth/microsoft/callback?code=x&state={state}", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("http://localhost:3000/login?error=")
