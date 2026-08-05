from datetime import datetime, timezone

from app.models import EventType, NotificationChannel, NotificationLog, NotificationStatus, StatusEvent, Vessel
from app.services import notification_service


def _vessel_with_event(db_session, event_type=EventType.ARRIVED_DESTINATION, destination="Pasir Gudang"):
    vessel = Vessel(name="MV ABC", imo_number="1234567", destination_port=destination)
    db_session.add(vessel)
    db_session.commit()
    db_session.refresh(vessel)

    event = StatusEvent(
        vessel_id=vessel.id,
        event_type=event_type,
        current_location=destination,
        last_event_text=f"Arrived {destination}",
        source_name="Mock Tracking Feed",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return vessel, event


def test_get_settings_creates_singleton_with_all_channels_disabled_by_default(db_session):
    settings = notification_service.get_settings(db_session)
    assert settings.id == 1
    assert settings.email_enabled is False
    assert settings.teams_enabled is False
    assert settings.daily_report_enabled is False

    # Calling again must return the same row, not create a second one.
    again = notification_service.get_settings(db_session)
    assert again.id == settings.id


def test_notify_vessel_event_does_nothing_when_both_channels_disabled(db_session):
    vessel, event = _vessel_with_event(db_session)
    notification_service.notify_vessel_event(db_session, vessel, event)
    assert db_session.query(NotificationLog).count() == 0


def test_notify_vessel_event_logs_skipped_when_enabled_but_unconfigured(db_session):
    settings = notification_service.get_settings(db_session)
    settings.email_enabled = True
    settings.teams_enabled = True
    db_session.commit()

    vessel, event = _vessel_with_event(db_session)
    notification_service.notify_vessel_event(db_session, vessel, event)

    logs = db_session.query(NotificationLog).order_by(NotificationLog.channel).all()
    assert len(logs) == 2
    assert {log.channel for log in logs} == {NotificationChannel.EMAIL, NotificationChannel.TEAMS}
    assert all(log.status == NotificationStatus.SKIPPED for log in logs)
    assert all(log.vessel_imo == "1234567" for log in logs)


def test_notify_vessel_event_arrived_at_destination_subject_calls_it_out_specifically(db_session):
    settings = notification_service.get_settings(db_session)
    settings.teams_enabled = True
    db_session.commit()

    vessel, event = _vessel_with_event(db_session, event_type=EventType.ARRIVED_DESTINATION)
    notification_service.notify_vessel_event(db_session, vessel, event)

    log = db_session.query(NotificationLog).one()
    assert "Arrived at Destination" in log.subject


def test_notify_vessel_event_sends_email_via_smtp(db_session, monkeypatch):
    settings = notification_service.get_settings(db_session)
    settings.email_enabled = True
    settings.smtp_host = "localhost"
    settings.smtp_from_address = "alerts@example.com"
    settings.email_recipients = "ops@example.com, second@example.com"
    db_session.commit()

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            sent["starttls"] = True

        def sendmail(self, from_addr, to_addrs, message):
            sent["from"] = from_addr
            sent["to"] = to_addrs
            sent["message"] = message

    monkeypatch.setattr("app.services.notification_service.smtplib.SMTP", FakeSMTP)

    vessel, event = _vessel_with_event(db_session)
    notification_service.notify_vessel_event(db_session, vessel, event)

    log = db_session.query(NotificationLog).one()
    assert log.status == NotificationStatus.SENT
    assert sent["to"] == ["ops@example.com", "second@example.com"]
    assert sent["from"] == "alerts@example.com"


def test_notify_vessel_event_logs_failed_on_smtp_error(db_session, monkeypatch):
    settings = notification_service.get_settings(db_session)
    settings.email_enabled = True
    settings.smtp_host = "localhost"
    settings.smtp_from_address = "alerts@example.com"
    settings.email_recipients = "ops@example.com"
    db_session.commit()

    import smtplib

    class BrokenSMTP:
        def __init__(self, host, port, timeout=None):
            raise smtplib.SMTPConnectError(500, "connection refused")

    monkeypatch.setattr("app.services.notification_service.smtplib.SMTP", BrokenSMTP)

    vessel, event = _vessel_with_event(db_session)
    notification_service.notify_vessel_event(db_session, vessel, event)

    log = db_session.query(NotificationLog).one()
    assert log.status == NotificationStatus.FAILED
    assert log.detail


def test_notify_vessel_event_posts_to_teams_webhook(db_session, monkeypatch):
    settings = notification_service.get_settings(db_session)
    settings.teams_enabled = True
    settings.teams_webhook_url = "https://example.com/webhook"
    db_session.commit()

    posted = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout=None):
        posted["url"] = url
        posted["json"] = json
        return FakeResponse()

    monkeypatch.setattr("app.services.notification_service.httpx.post", fake_post)

    vessel, event = _vessel_with_event(db_session)
    notification_service.notify_vessel_event(db_session, vessel, event)

    log = db_session.query(NotificationLog).one()
    assert log.status == NotificationStatus.SENT
    assert posted["url"] == "https://example.com/webhook"
    assert "text" in posted["json"]


def test_send_test_notification_only_hits_enabled_channels(db_session, monkeypatch):
    settings = notification_service.get_settings(db_session)
    settings.teams_enabled = True
    settings.teams_webhook_url = "https://example.com/webhook"
    db_session.commit()

    class FakeResponse:
        def raise_for_status(self):
            return None

    monkeypatch.setattr("app.services.notification_service.httpx.post", lambda *a, **k: FakeResponse())

    entries = notification_service.send_test_notification(db_session)
    assert len(entries) == 1
    assert entries[0].channel == NotificationChannel.TEAMS
    assert entries[0].status == NotificationStatus.SENT
