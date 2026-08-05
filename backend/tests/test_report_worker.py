from datetime import datetime, timezone

from app.models import NotificationLog
from app.services import notification_service, report_worker


def test_tick_does_nothing_when_daily_report_disabled(db_session):
    report_worker.run_daily_report_tick()
    assert db_session.query(NotificationLog).count() == 0


def test_tick_does_nothing_outside_the_configured_hour(db_session, monkeypatch):
    settings = notification_service.get_settings(db_session)
    settings.daily_report_enabled = True
    settings.teams_enabled = True
    settings.teams_webhook_url = "https://example.com/webhook"
    # Pick an hour guaranteed not to be "now" (mod 24 so this is always a valid, different hour).
    wrong_hour = (datetime.now(timezone.utc).hour + 1) % 24
    settings.daily_report_hour_utc = wrong_hour
    db_session.commit()

    report_worker.run_daily_report_tick()
    assert db_session.query(NotificationLog).count() == 0


def test_tick_sends_once_at_the_configured_hour_and_not_again_same_day(db_session, monkeypatch):
    settings = notification_service.get_settings(db_session)
    settings.daily_report_enabled = True
    settings.teams_enabled = True
    settings.teams_webhook_url = "https://example.com/webhook"
    settings.daily_report_hour_utc = datetime.now(timezone.utc).hour
    db_session.commit()

    class FakeResponse:
        def raise_for_status(self):
            return None

    monkeypatch.setattr("app.services.notification_service.httpx.post", lambda *a, **k: FakeResponse())

    report_worker.run_daily_report_tick()
    assert db_session.query(NotificationLog).count() == 1

    # A second check within the same hour (simulating the next hourly tick still landing on
    # the same UTC day) must not send a duplicate.
    report_worker.run_daily_report_tick()
    assert db_session.query(NotificationLog).count() == 1


def test_send_daily_report_returns_log_entries(db_session, monkeypatch):
    settings = notification_service.get_settings(db_session)
    settings.teams_enabled = True
    settings.teams_webhook_url = "https://example.com/webhook"
    db_session.commit()

    class FakeResponse:
        def raise_for_status(self):
            return None

    monkeypatch.setattr("app.services.notification_service.httpx.post", lambda *a, **k: FakeResponse())

    entries = report_worker.send_daily_report(db_session, settings)
    assert len(entries) == 1
    assert entries[0].subject.startswith("Daily Vessel Report")
