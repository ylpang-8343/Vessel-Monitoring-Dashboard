"""Daily report scheduling (Section 7 / Phase 4's "generates daily reports"). Delivered via the
same two channels as event notifications (Section 6.C): the full report as an Excel attachment
by email, and a short text summary posted to Teams (Teams webhooks aren't a great fit for
delivering a binary file, so the report proper always goes out by email if enabled).

Scheduling approach: rather than reconfiguring APScheduler's cron trigger every time an admin
changes the report hour in Settings, a single lightweight hourly job (`run_daily_report_tick`)
just checks "has the configured hour arrived, and have we not already sent today" - simpler to
reason about and test than dynamic job rescheduling, at the cost of a report being sent up to
~59 minutes after its nominal hour rather than exactly on it (immaterial for a *daily* report).
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import NotificationChannel, NotificationLog, NotificationSettings
from app.services.notification_service import get_settings, log_notification, send_email_with_attachment, send_teams_message
from app.services.report_service import build_excel_report, build_report_summary

logger = logging.getLogger("report_worker")

# Separate scheduler from tracking_worker's - a distinct concern (once-an-hour report check vs.
# the tracking poll's own interval) kept on its own APScheduler instance rather than sharing
# one, so each can be started/stopped/tested independently.
_scheduler: BackgroundScheduler | None = None


def _summary_text(active: int, eta: int, arrived: int) -> str:
    return f"Active: {active} · ETA to Destination: {eta} · Arrived at Destination: {arrived}"


def send_daily_report(db: Session, settings: NotificationSettings | None = None) -> list[NotificationLog]:
    """Build the report and deliver it through every enabled channel right now, regardless of
    schedule. Used by both the hourly tick below (once it decides it's time) and the admin's
    "Send Now" button in Settings → Notifications (routers/notifications.py) for on-demand
    testing without waiting for the scheduled hour. Returns the log entries created, the same
    shape notification_service.send_test_notification() uses, so the API response for both
    "test" and "send now" can share one frontend rendering path."""
    settings = settings or get_settings(db)
    summary = build_report_summary(db)
    subject = f"Daily Vessel Report — {summary.generated_at.strftime('%d %b %Y')}"
    body = (
        f"Daily report generated {summary.generated_at.strftime('%d %b %Y, %H:%M UTC')}.\n"
        + _summary_text(len(summary.active), len(summary.eta_to_destination), len(summary.arrived_at_destination))
    )
    entries: list[NotificationLog] = []

    if settings.email_enabled:
        excel_bytes = build_excel_report(summary)
        status, detail = send_email_with_attachment(settings, subject, body, "vessel-report.xlsx", excel_bytes)
        entries.append(log_notification(db, NotificationChannel.EMAIL, status, subject, body, detail=detail))

    if settings.teams_enabled:
        status, detail = send_teams_message(settings, f"{subject}\n{body}")
        entries.append(log_notification(db, NotificationChannel.TEAMS, status, subject, body, detail=detail))

    return entries


def run_daily_report_tick() -> None:
    """Scheduled once an hour (see start_scheduler below) - sends the daily report at most once
    per day, on the admin-configured UTC hour."""
    db = SessionLocal()
    try:
        settings = get_settings(db)
        if not settings.daily_report_enabled:
            return

        now = datetime.now(timezone.utc)
        if now.hour != settings.daily_report_hour_utc:
            return

        today = now.strftime("%Y-%m-%d")
        if settings.daily_report_last_sent_date == today:
            # Already sent within this same hour-window today - the hourly tick would
            # otherwise resend on every check during the configured hour.
            return

        try:
            send_daily_report(db, settings)
        except Exception:
            logger.exception("daily report send failed")
        finally:
            # Mark as sent for today even on failure, so a persistently broken config logs one
            # FAILED entry per day (visible in the notification log) rather than retrying every
            # hour for the rest of the day.
            settings.daily_report_last_sent_date = today
            db.commit()
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """Start the hourly report-check job (idempotent, same pattern as
    tracking_worker.start_scheduler). Called from app/main.py's startup lifespan."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_report_tick, "interval", hours=1, id="daily_report_tick")
    scheduler.start()
    # Fire one check immediately on startup too - otherwise a backend that (re)starts during the
    # configured report hour would wait up to an hour before its first check that day.
    scheduler.modify_job("daily_report_tick", next_run_time=datetime.now())
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    """Stop the hourly report-check job. Called from app/main.py's shutdown lifespan; also
    monkeypatched to a no-op in tests (see tests/conftest.py)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
