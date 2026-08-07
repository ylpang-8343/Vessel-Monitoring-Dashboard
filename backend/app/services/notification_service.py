"""Automated notifications (Section 6.C): email, Microsoft Teams, and WhatsApp, triggered on
vessel arrival/departure events (including the headline "arrived at destination" case), on
detected exceptions (Phase 6), and on the daily report (see report_service.py /
report_worker.py).

**Scope note, updated in Phase 6.** Delay notifications were previously out of scope because
nothing in the app captured a *planned* ETA to compare against, and Section 3.10 argues against
guessing at what tracking data can't confirm. Phase 6 removes that blocker rather than working
around it: tracking sources now report an ETA per event (StatusEvent.eta), so "delayed" is
arithmetic against a real reported time and delay alerts arrive here through the exception
pipeline (services/exception_detector.py). ETA-*change* notifications remain unimplemented -
they'd fire on every routine source revision, which is noise rather than signal.

WhatsApp - the proposal's own Figure 5 labels it "planned for phase 2 rollout" - is delivered
here in Phase 6 as a third channel alongside email and Teams.

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

from app.models import (
    EventType,
    NotificationChannel,
    NotificationLog,
    NotificationSettings,
    NotificationStatus,
    StatusEvent,
    Vessel,
    VesselException,
)

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


# Meta's WhatsApp Business Cloud API. Pinned to a specific version rather than "latest" so a
# Meta-side release can't silently change the request shape under a running deployment.
WHATSAPP_API_BASE_URL = "https://graph.facebook.com/v21.0"


def send_whatsapp_message(settings: NotificationSettings, text: str) -> tuple[NotificationStatus, str | None]:
    """Attempt to send one WhatsApp message per configured recipient via the WhatsApp Business
    Cloud API (Phase 6 / the proposal's Figure 5 "future enhancement").

    Unlike email and Teams, this API takes one recipient per request, so N recipients means N
    calls. The result is aggregated: any recipient failing marks the whole attempt FAILED with
    the offending numbers in the detail, so a partial delivery is never silently reported as a
    clean success.
    """
    if not settings.whatsapp_phone_number_id or not settings.whatsapp_access_token:
        return NotificationStatus.SKIPPED, "WhatsApp enabled but phone number ID / access token not configured"

    recipients = [number.strip() for number in (settings.whatsapp_recipients or "").split(",") if number.strip()]
    if not recipients:
        return NotificationStatus.SKIPPED, "No WhatsApp recipients configured"

    url = f"{WHATSAPP_API_BASE_URL}/{settings.whatsapp_phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    failures: list[str] = []

    for number in recipients:
        payload = {
            "messaging_product": "whatsapp",
            "to": number,
            "type": "text",
            "text": {"body": text},
        }
        try:
            # Same short timeout as the Teams webhook - a hanging provider must not stall the
            # tracking-poll tick that triggered this.
            response = httpx.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            failures.append(f"{number}: {exc}")

    if failures:
        return NotificationStatus.FAILED, "; ".join(failures)
    return NotificationStatus.SENT, None


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


def dispatch_to_enabled_channels(
    db: Session,
    subject: str,
    body: str,
    vessel: Vessel | None = None,
) -> list[NotificationLog]:
    """Send one message through every *enabled* channel and log each attempt.

    Single place where "which channels are on, and how does each one want the message" is
    decided - so vessel events, exception alerts, and the manual test button can't drift apart
    in which channels they honour. Email gets subject and body as separate fields; Teams and
    WhatsApp are plain-text surfaces, so the subject is prepended to the body for them.
    """
    settings = get_settings(db)
    combined = f"{subject}\n{body}"
    entries: list[NotificationLog] = []

    if settings.email_enabled:
        status, detail = _send_email(settings, subject, body)
        entries.append(log_notification(db, NotificationChannel.EMAIL, status, subject, body, vessel=vessel, detail=detail))

    if settings.teams_enabled:
        status, detail = send_teams_message(settings, combined)
        entries.append(log_notification(db, NotificationChannel.TEAMS, status, subject, body, vessel=vessel, detail=detail))

    if settings.whatsapp_enabled:
        status, detail = send_whatsapp_message(settings, combined)
        entries.append(
            log_notification(db, NotificationChannel.WHATSAPP, status, subject, body, vessel=vessel, detail=detail)
        )

    return entries


def notify_vessel_event(db: Session, vessel: Vessel, event: StatusEvent) -> None:
    """Send (or log skipping/failing to send) a notification for one new StatusEvent, through
    every enabled channel. Called from tracking_worker.run_tracking_poll() right after each
    event is persisted - wrapped there in a try/except so a notification problem never blocks
    tracking updates themselves."""
    subject, body = _build_event_message(vessel, event)
    dispatch_to_enabled_channels(db, subject, body, vessel=vessel)


def notify_exception(db: Session, vessel: Vessel, exception: VesselException) -> None:
    """Notify about one newly-detected exception (Phase 6 / Section 7's "AI Exception Alerts").
    Called from the tracking-poll tick for each *newly created* VesselException, so an ongoing
    condition alerts once rather than every tick - the dedupe key in exception_detector.py is
    what guarantees that, not this function."""
    kind_label = exception.kind.value.replace("_", " ").title()
    subject = f"Exception — {kind_label}: {vessel.name}"
    body = (
        f"{vessel.name} (IMO {vessel.imo_number}): {exception.message}\n"
        f"Destination: {vessel.destination_port or 'Not set'}"
    )
    dispatch_to_enabled_channels(db, subject, body, vessel=vessel)


def send_test_notification(db: Session) -> list[NotificationLog]:
    """Send a one-off test message through every *enabled* channel immediately, regardless of
    any real vessel event - lets an admin confirm their SMTP/Teams/WhatsApp config actually
    works right after saving it, rather than waiting for the next real tracking event."""
    subject = "Test Notification — Vessel Monitoring Dashboard"
    body = f"This is a test notification sent from Settings → Notifications at {datetime.now(timezone.utc).isoformat()}."
    return dispatch_to_enabled_channels(db, subject, body)
