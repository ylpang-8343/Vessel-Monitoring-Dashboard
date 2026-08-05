"""Automated notifications (Section 6.C): email and Microsoft Teams, triggered on vessel
arrival/departure events (including the headline "arrived at destination" case) and on the
daily report (see report_service.py / report_worker.py).

Deliberately out of scope, matching Section 3.10's reasoning for the dashboard's own status
values: ETA-change and delay notifications. Both would require comparing against a *planned*
ETA the app doesn't capture anywhere, and Section 3.10 already recommends against guessing at
things AIS-style tracking data can't reliably confirm - the same logic applies here. WhatsApp is
also out of scope - the proposal itself labels it "planned for phase 2 rollout" (i.e. a future
enhancement, not this phase).

Every send attempt is logged to NotificationLog (sent/skipped/failed) so Settings → Notifications
gives an admin a clear, honest picture of what's actually happening - the same "unavailable
rather than silently broken" posture as PDF extraction without an API key.
"""

import smtplib
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
from sqlalchemy.orm import Session

from app.models import EventType, NotificationChannel, NotificationLog, NotificationSettings, NotificationStatus, StatusEvent, Vessel

# Singleton row id - see NotificationSettings' docstring in models.py for why this is a
# singleton rather than a list like TrackingSource.
SETTINGS_ID = 1


def get_settings(db: Session) -> NotificationSettings:
    """Fetch the one NotificationSettings row, creating it with all-disabled defaults on first
    use so callers never have to handle "no settings row yet" as a special case."""
    settings = db.query(NotificationSettings).filter(NotificationSettings.id == SETTINGS_ID).first()
    if settings is None:
        settings = NotificationSettings(id=SETTINGS_ID)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def log_notification(
    db: Session,
    channel: NotificationChannel,
    status: NotificationStatus,
    subject: str,
    message: str,
    vessel: Vessel | None = None,
    detail: str | None = None,
) -> NotificationLog:
    """Record one send attempt (whatever the outcome) - the source of truth behind Settings →
    Notifications' "recent activity" table. Public (not `_`-prefixed) since both this module and
    services/report_worker.py write to it."""
    entry = NotificationLog(
        channel=channel,
        status=status,
        subject=subject,
        message=message,
        vessel_name=vessel.name if vessel else None,
        vessel_imo=vessel.imo_number if vessel else None,
        detail=detail,
    )
    db.add(entry)
    db.commit()
    return entry


def _send_email(settings: NotificationSettings, subject: str, body: str) -> tuple[NotificationStatus, str | None]:
    """Attempt to send one plain-text email via the configured SMTP server. Returns (status,
    detail) rather than raising, so a bad SMTP config never propagates up into the tracking-poll
    loop that triggered it."""
    if not settings.smtp_host or not settings.smtp_from_address or not settings.email_recipients:
        return NotificationStatus.SKIPPED, "Email enabled but SMTP host/from address/recipients not fully configured"

    recipients = [addr.strip() for addr in settings.email_recipients.split(",") if addr.strip()]
    if not recipients:
        return NotificationStatus.SKIPPED, "No email recipients configured"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = ", ".join(recipients)

    return _deliver(settings, recipients, msg)


def send_email_with_attachment(
    settings: NotificationSettings,
    subject: str,
    body: str,
    attachment_name: str,
    attachment_bytes: bytes,
) -> tuple[NotificationStatus, str | None]:
    """Like _send_email, but with one binary attachment - used for the daily report's Excel
    file (services/report_worker.py). Exported (not `_`-prefixed) for that cross-module use."""
    if not settings.smtp_host or not settings.smtp_from_address or not settings.email_recipients:
        return NotificationStatus.SKIPPED, "Email enabled but SMTP host/from address/recipients not fully configured"

    recipients = [addr.strip() for addr in settings.email_recipients.split(",") if addr.strip()]
    if not recipients:
        return NotificationStatus.SKIPPED, "No email recipients configured"

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_address
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(body))
    attachment = MIMEApplication(attachment_bytes, Name=attachment_name)
    attachment["Content-Disposition"] = f'attachment; filename="{attachment_name}"'
    msg.attach(attachment)

    return _deliver(settings, recipients, msg)


def _deliver(settings: NotificationSettings, recipients: list[str], msg: MIMEText | MIMEMultipart) -> tuple[NotificationStatus, str | None]:
    """Shared SMTP connect/send/close logic for both plain and attachment emails."""
    try:
        # A short timeout keeps a misbehaving/unreachable SMTP server from stalling the
        # tracking-poll tick (or hourly report check) that's waiting on this call.
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.sendmail(settings.smtp_from_address, recipients, msg.as_string())
        return NotificationStatus.SENT, None
    except (smtplib.SMTPException, OSError) as exc:
        return NotificationStatus.FAILED, str(exc)


def send_teams_message(settings: NotificationSettings, text: str) -> tuple[NotificationStatus, str | None]:
    """Attempt to post one message to the configured Microsoft Teams incoming webhook. Teams
    webhooks accept a simple `{"text": "..."}` payload for a plain-text card - good enough for
    both event alerts and the daily report's text summary (the report's actual data goes out as
    an Excel email attachment instead; see services/report_worker.py)."""
    if not settings.teams_webhook_url:
        return NotificationStatus.SKIPPED, "Teams enabled but no webhook URL configured"

    try:
        response = httpx.post(settings.teams_webhook_url, json={"text": text}, timeout=10)
        response.raise_for_status()
        return NotificationStatus.SENT, None
    except httpx.HTTPError as exc:
        return NotificationStatus.FAILED, str(exc)


def _build_event_message(vessel: Vessel, event: StatusEvent) -> tuple[str, str]:
    """Build the (subject, body) for a vessel status-event notification, mirroring the example
    wording in the proposal's Figure 5 ("Vessel Arrival — MV Ocean Pearl ... has arrived at
    Pasir Gudang")."""
    if event.event_type == EventType.ARRIVED_DESTINATION:
        subject = f"Vessel Arrived at Destination — {vessel.name}"
    elif event.event_type == EventType.AT_PORT:
        subject = f"Vessel Arrival — {vessel.name}"
    elif event.event_type == EventType.SAILED_FROM_DESTINATION:
        subject = f"Vessel Departed Destination — {vessel.name}"
    else:  # SAILING or ETA_DESTINATION
        subject = f"Vessel Departure — {vessel.name}"

    body = (
        f"{vessel.name} (IMO {vessel.imo_number}): {event.last_event_text}\n"
        f"Destination: {vessel.destination_port or 'Not set'}\n"
        f"Source: {event.source_name}"
    )
    return subject, body


def notify_vessel_event(db: Session, vessel: Vessel, event: StatusEvent) -> None:
    """Send (or log skipping/failing to send) a notification for one new StatusEvent, through
    every enabled channel. Called from tracking_worker.run_tracking_poll() right after each
    event is persisted - wrapped there in a try/except so a notification problem never blocks
    tracking updates themselves."""
    settings = get_settings(db)
    subject, body = _build_event_message(vessel, event)

    if settings.email_enabled:
        status, detail = _send_email(settings, subject, body)
        log_notification(db, NotificationChannel.EMAIL, status, subject, body, vessel=vessel, detail=detail)

    if settings.teams_enabled:
        status, detail = send_teams_message(settings, f"{subject}\n{body}")
        log_notification(db, NotificationChannel.TEAMS, status, subject, body, vessel=vessel, detail=detail)


def send_test_notification(db: Session) -> list[NotificationLog]:
    """Send a one-off test message through every *enabled* channel immediately, regardless of
    any real vessel event - lets an admin confirm their SMTP/Teams config actually works right
    after saving it, rather than waiting for the next real tracking event."""
    settings = get_settings(db)
    subject = "Test Notification — Vessel Monitoring Dashboard"
    body = f"This is a test notification sent from Settings → Notifications at {datetime.now(timezone.utc).isoformat()}."
    entries: list[NotificationLog] = []

    if settings.email_enabled:
        status, detail = _send_email(settings, subject, body)
        entries.append(log_notification(db, NotificationChannel.EMAIL, status, subject, body, detail=detail))

    if settings.teams_enabled:
        status, detail = send_teams_message(settings, f"{subject}\n{body}")
        entries.append(log_notification(db, NotificationChannel.TEAMS, status, subject, body, detail=detail))

    return entries
