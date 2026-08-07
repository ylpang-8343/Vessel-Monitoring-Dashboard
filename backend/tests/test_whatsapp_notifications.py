"""WhatsApp channel (Phase 6) - the proposal's Figure 5 "future enhancement", delivered via
Meta's WhatsApp Business Cloud API."""

from datetime import datetime, timezone

import httpx

from app.models import EventType, ExceptionKind, NotificationChannel, NotificationLog, NotificationStatus, StatusEvent, Vessel, VesselException
from app.services import notification_service


def _configure_whatsapp(db_session, **overrides):
    settings = notification_service.get_settings(db_session)
    settings.whatsapp_enabled = True
    settings.whatsapp_phone_number_id = "1234567890"
    settings.whatsapp_access_token = "test-token"
    settings.whatsapp_recipients = "+60123456789"
    for field, value in overrides.items():
        setattr(settings, field, value)
    db_session.commit()
    return settings


def test_skipped_when_credentials_are_missing(db_session):
    settings = _configure_whatsapp(db_session, whatsapp_access_token=None)
    status, detail = notification_service.send_whatsapp_message(settings, "hello")
    assert status == NotificationStatus.SKIPPED
    assert "access token" in detail


def test_skipped_when_no_recipients(db_session):
    settings = _configure_whatsapp(db_session, whatsapp_recipients="  ")
    status, detail = notification_service.send_whatsapp_message(settings, "hello")
    assert status == NotificationStatus.SKIPPED
    assert "recipients" in detail


def test_posts_one_request_per_recipient_in_the_cloud_api_shape(db_session, monkeypatch):
    settings = _configure_whatsapp(db_session, whatsapp_recipients="+60123456789, +6598765432")
    calls = []

    def _fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers})
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.services.notification_service.httpx.post", _fake_post)

    status, detail = notification_service.send_whatsapp_message(settings, "Vessel Arrival — MV ABC")

    assert status == NotificationStatus.SENT and detail is None
    # One API call per recipient - the Cloud API takes a single `to` per request.
    assert [call["json"]["to"] for call in calls] == ["+60123456789", "+6598765432"]
    assert calls[0]["url"].endswith("/1234567890/messages")
    assert calls[0]["headers"]["Authorization"] == "Bearer test-token"
    assert calls[0]["json"]["messaging_product"] == "whatsapp"
    assert calls[0]["json"]["text"]["body"] == "Vessel Arrival — MV ABC"


def test_partial_delivery_is_reported_as_failed_not_sent(db_session, monkeypatch):
    # A run where one number succeeds and one fails must not be logged as a clean success.
    settings = _configure_whatsapp(db_session, whatsapp_recipients="+60123456789, +6598765432")

    def _fake_post(url, json=None, headers=None, timeout=None):
        if json["to"] == "+6598765432":
            raise httpx.ConnectError("unreachable")
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.services.notification_service.httpx.post", _fake_post)

    status, detail = notification_service.send_whatsapp_message(settings, "hello")
    assert status == NotificationStatus.FAILED
    assert "+6598765432" in detail
    assert "+60123456789" not in detail


def test_http_error_response_is_failed(db_session, monkeypatch):
    settings = _configure_whatsapp(db_session)

    def _fake_post(url, json=None, headers=None, timeout=None):
        return httpx.Response(401, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.services.notification_service.httpx.post", _fake_post)

    status, detail = notification_service.send_whatsapp_message(settings, "hello")
    assert status == NotificationStatus.FAILED
    assert detail


def test_vessel_event_notification_goes_out_over_whatsapp(db_session, monkeypatch):
    _configure_whatsapp(db_session)
    monkeypatch.setattr(
        "app.services.notification_service.httpx.post",
        lambda url, json=None, headers=None, timeout=None: httpx.Response(200, request=httpx.Request("POST", url)),
    )

    vessel = Vessel(name="MV ABC", imo_number="1234567", destination_port="Pasir Gudang")
    db_session.add(vessel)
    db_session.commit()
    db_session.refresh(vessel)
    event = StatusEvent(
        vessel_id=vessel.id,
        event_type=EventType.ARRIVED_DESTINATION,
        current_location="Pasir Gudang",
        last_event_text="Arrived Pasir Gudang",
        source_name="Mock Tracking Feed",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    notification_service.notify_vessel_event(db_session, vessel, event)

    logs = db_session.query(NotificationLog).filter(NotificationLog.channel == NotificationChannel.WHATSAPP).all()
    assert len(logs) == 1
    assert logs[0].status == NotificationStatus.SENT
    assert logs[0].vessel_imo == "1234567"


def test_exception_alert_is_notified_through_enabled_channels(db_session, monkeypatch):
    _configure_whatsapp(db_session)
    monkeypatch.setattr(
        "app.services.notification_service.httpx.post",
        lambda url, json=None, headers=None, timeout=None: httpx.Response(200, request=httpx.Request("POST", url)),
    )

    vessel = Vessel(name="MV Late", imo_number="2233445", destination_port="Butterworth")
    db_session.add(vessel)
    db_session.commit()
    db_session.refresh(vessel)

    exception = VesselException(
        vessel_id=vessel.id,
        kind=ExceptionKind.DELAYED,
        message="Arrived at Butterworth 6h 0m after the reported ETA",
        dedupe_key="test-key",
    )
    db_session.add(exception)
    db_session.commit()

    notification_service.notify_exception(db_session, vessel, exception)

    log = db_session.query(NotificationLog).filter(NotificationLog.channel == NotificationChannel.WHATSAPP).one()
    assert log.status == NotificationStatus.SENT
    assert "Delayed" in log.subject
    assert "6h 0m after the reported ETA" in log.message


def test_notification_settings_api_masks_the_access_token(admin_client):
    admin_client.patch(
        "/api/notifications/settings",
        json={
            "whatsapp_enabled": True,
            "whatsapp_phone_number_id": "1234567890",
            "whatsapp_access_token": "super-secret",
            "whatsapp_recipients": "+60123456789",
        },
    )
    body = admin_client.get("/api/notifications/settings").json()

    assert body["whatsapp_enabled"] is True
    assert body["whatsapp_phone_number_id"] == "1234567890"
    assert body["whatsapp_access_token_set"] is True
    # The token itself must never round-trip back to the browser.
    assert "whatsapp_access_token" not in body
    assert "super-secret" not in str(body)


def test_blank_access_token_on_save_leaves_the_stored_one_intact(admin_client, db_session):
    admin_client.patch("/api/notifications/settings", json={"whatsapp_access_token": "keep-me"})
    # Re-saving the card without re-entering the token (field omitted) must not wipe it.
    admin_client.patch("/api/notifications/settings", json={"whatsapp_enabled": True})

    assert notification_service.get_settings(db_session).whatsapp_access_token == "keep-me"
