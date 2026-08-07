"""Admin-only notification/report configuration (Section 6.C, Phase 4's daily report), backing
Settings → Notifications. Gated the same way as routers/users.py - `Depends(require_admin)` at
the router level covers every route here automatically."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_admin
from app.models import NotificationLog
from app.schemas import NotificationLogOut, NotificationSettingsOut, NotificationSettingsUpdate
from app.services.notification_service import get_settings, send_test_notification
from app.services.report_worker import send_daily_report

router = APIRouter(prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(require_admin)])


def _to_settings_out(settings) -> NotificationSettingsOut:
    """Build the response shape, masking stored secrets (the SMTP password and the WhatsApp
    access token) behind booleans rather than ever sending them back to the browser - see
    NotificationSettingsOut's docstring."""
    return NotificationSettingsOut(
        email_enabled=settings.email_enabled,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password_set=bool(settings.smtp_password),
        smtp_from_address=settings.smtp_from_address,
        email_recipients=settings.email_recipients,
        teams_enabled=settings.teams_enabled,
        teams_webhook_url=settings.teams_webhook_url,
        whatsapp_enabled=settings.whatsapp_enabled,
        whatsapp_phone_number_id=settings.whatsapp_phone_number_id,
        whatsapp_access_token_set=bool(settings.whatsapp_access_token),
        whatsapp_recipients=settings.whatsapp_recipients,
        daily_report_enabled=settings.daily_report_enabled,
        daily_report_hour_utc=settings.daily_report_hour_utc,
        daily_report_last_sent_date=settings.daily_report_last_sent_date,
    )


@router.get("/settings", response_model=NotificationSettingsOut)
def get_notification_settings(db: Session = Depends(get_db)):
    return _to_settings_out(get_settings(db))


@router.patch("/settings", response_model=NotificationSettingsOut)
def update_notification_settings(payload: NotificationSettingsUpdate, db: Session = Depends(get_db)):
    """Partial update - only fields the client actually sent are touched (mirrors
    routers/tracking_sources.py's PATCH), so the Email and Teams cards on the frontend can each
    save independently."""
    settings = get_settings(db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return _to_settings_out(settings)


@router.get("/log", response_model=list[NotificationLogOut])
def list_notification_log(limit: int = 50, db: Session = Depends(get_db)):
    """Most recent notification attempts first, so an admin can see at a glance whether
    channels are actually working (or exactly why they aren't)."""
    return db.query(NotificationLog).order_by(NotificationLog.created_at.desc()).limit(limit).all()


@router.post("/test", response_model=list[NotificationLogOut])
def test_notifications(db: Session = Depends(get_db)):
    """Send a one-off test message through every enabled channel right now - lets an admin
    confirm their SMTP/Teams config actually works immediately after saving it."""
    return send_test_notification(db)


@router.post("/send-daily-report", response_model=list[NotificationLogOut])
def send_daily_report_now(db: Session = Depends(get_db)):
    """Trigger the daily report immediately, bypassing the scheduled hour - the "Send Now"
    button, mainly useful for verifying the whole report pipeline without waiting for the
    configured hour to arrive."""
    return send_daily_report(db)
