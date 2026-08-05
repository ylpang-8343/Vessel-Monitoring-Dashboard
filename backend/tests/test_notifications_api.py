def test_unauthenticated_request_rejected():
    from fastapi.testclient import TestClient

    from app.main import app

    anon_client = TestClient(app)
    assert anon_client.get("/api/notifications/settings").status_code == 401


def test_non_admin_user_forbidden(client):
    assert client.get("/api/notifications/settings").status_code == 403


def test_get_settings_defaults_and_never_returns_raw_password(admin_client):
    resp = admin_client.get("/api/notifications/settings")
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_enabled"] is False
    assert body["smtp_password_set"] is False
    assert "smtp_password" not in body


def test_patch_settings_updates_only_provided_fields(admin_client):
    resp = admin_client.patch(
        "/api/notifications/settings",
        json={"email_enabled": True, "smtp_host": "smtp.example.com", "smtp_password": "hunter2"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["email_enabled"] is True
    assert body["smtp_host"] == "smtp.example.com"
    # Password was set but is never echoed back - only whether one is set.
    assert body["smtp_password_set"] is True
    assert "smtp_password" not in body

    # A second PATCH that doesn't mention smtp_host must leave it untouched.
    resp2 = admin_client.patch("/api/notifications/settings", json={"teams_enabled": True})
    assert resp2.status_code == 200
    assert resp2.json()["smtp_host"] == "smtp.example.com"
    assert resp2.json()["teams_enabled"] is True


def test_daily_report_hour_out_of_range_rejected(admin_client):
    resp = admin_client.patch("/api/notifications/settings", json={"daily_report_hour_utc": 24})
    assert resp.status_code == 422


def test_log_endpoint_reflects_test_send_attempts(admin_client, monkeypatch):
    admin_client.patch(
        "/api/notifications/settings",
        json={"teams_enabled": True, "teams_webhook_url": "https://example.com/webhook"},
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

    monkeypatch.setattr("app.services.notification_service.httpx.post", lambda *a, **k: FakeResponse())

    send_resp = admin_client.post("/api/notifications/test")
    assert send_resp.status_code == 200
    assert len(send_resp.json()) == 1

    log_resp = admin_client.get("/api/notifications/log")
    assert log_resp.status_code == 200
    entries = log_resp.json()
    assert len(entries) == 1
    assert entries[0]["channel"] == "teams"
    assert entries[0]["status"] == "sent"


def test_send_daily_report_now_via_email_with_no_vessels(admin_client, monkeypatch):
    admin_client.patch(
        "/api/notifications/settings",
        json={
            "email_enabled": True,
            "smtp_host": "localhost",
            "smtp_from_address": "alerts@example.com",
            "email_recipients": "ops@example.com",
        },
    )

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def sendmail(self, *a, **k):
            pass

    monkeypatch.setattr("app.services.notification_service.smtplib.SMTP", FakeSMTP)

    resp = admin_client.post("/api/notifications/send-daily-report")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["channel"] == "email"
    assert entries[0]["status"] == "sent"
