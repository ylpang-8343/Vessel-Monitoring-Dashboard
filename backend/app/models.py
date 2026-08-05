"""SQLAlchemy ORM models - the database schema.

Tables are created automatically at backend startup via `Base.metadata.create_all()`
(see app/main.py's `lifespan`). That call only *adds* new tables/columns that don't exist yet;
it never alters an existing table, so a schema change on a database that already has the old
shape needs a volume reset in dev (see README.md) or a real migration tool in production.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EventType(str, enum.Enum):
    """The five statuses a vessel's latest tracked event can be in (Section 3.3a / 3.10).

    Deliberately limited to what tracking data can reliably confirm - no "delayed" or
    "loading/discharging" guesswork (see Section 3.10's recommendation).
    """

    SAILING = "sailing"
    AT_PORT = "at_port"
    ETA_DESTINATION = "eta_destination"
    ARRIVED_DESTINATION = "arrived_destination"
    SAILED_FROM_DESTINATION = "sailed_from_destination"


class SourceKind(str, enum.Enum):
    """What a TrackingSource feeds: vessel-position data (Section 3.3) vs. the future
    container/booking module (Section 4)."""

    VESSEL = "vessel"
    CONTAINER = "container"


class UserRole(str, enum.Enum):
    """Two roles only. There is no path to become ADMIN by self-registering - see
    app/routers/auth.py and app/cli.py."""

    USER = "user"
    ADMIN = "admin"


class User(Base):
    """A login account. Registration always creates a USER; the first ADMIN is bootstrapped via
    the `promote-admin` CLI command, and every admin after that via the Settings → Users tab."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # bcrypt hash - the plaintext password is never stored.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.USER)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vessel(Base):
    """A monitored vessel (Section 3.1). Its "current status" is derived from the most recent
    row in `events`, not stored redundantly on this table - see services/presentation.py."""

    __tablename__ = "vessels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    imo_number: Mapped[str] = mapped_column(String(7), unique=True, index=True, nullable=False)
    # Optional (Section 3.1) - when unset, the vessel is tracked but never enters the ETA/Arrived
    # states and is never auto-archived (Section 3.7).
    destination_port: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set once the vessel is archived (auto via Section 3.7, or manually via Section 3.8);
    # NULL means still actively tracked/monitored.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Ordered oldest-to-newest so `events[-1]` is always the latest event; deleting a vessel
    # cascades to delete its whole history with it.
    events: Mapped[list["StatusEvent"]] = relationship(
        back_populates="vessel", cascade="all, delete-orphan", order_by="StatusEvent.occurred_at"
    )


class StatusEvent(Base):
    """One tracked update for a vessel (Section 3.5/3.6) - e.g. "Arrived Pasir Gudang". Rows
    are append-only: nothing here is ever edited or deleted, so the full movement history stays
    intact even after the vessel itself is archived."""

    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vessel_id: Mapped[int] = mapped_column(ForeignKey("vessels.id"), nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    current_location: Mapped[str] = mapped_column(String(160), nullable=False)
    # Human-readable summary shown directly in the dashboard's "Last Event" column, e.g.
    # "Arrived Shanghai — 20 Jul 2026, 08:00" (Section 3.4).
    last_event_text: Mapped[str] = mapped_column(String(200), nullable=False)
    # Which tracking source reported this event (Section 3.3's "tagged with its originating
    # data source" requirement).
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    # When the event actually happened, per the source's report.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # When our own tracking worker recorded it - usually close to occurred_at, but kept
    # separate in case a source ever reports events out of order or with a delay.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vessel: Mapped["Vessel"] = relationship(back_populates="events")


class TrackingSource(Base):
    """A vessel-tracking website/feed, manageable by admins via Settings (Section 3.9). Only
    rows with `adapter_key="mock"` are actually polled right now - see sources/mock_adapter.py
    and the module docstring on services/tracking_worker.py for why."""

    __tablename__ = "tracking_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind), nullable=False, default=SourceKind.VESSEL)
    # Which TrackingSourceAdapter implementation drives this source; "mock" is the only one
    # actually wired up to poll (see sources/base.py for the pluggable-adapter interface).
    adapter_key: Mapped[str] = mapped_column(String(40), nullable=False, default="mock")
    # Admin on/off toggle - the tracking worker skips disabled sources entirely.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NotificationChannel(str, enum.Enum):
    """The two channels Section 6.C calls out as available "at launch" - WhatsApp is explicitly
    scoped as a future enhancement in the proposal, so it isn't modelled here at all."""

    EMAIL = "email"
    TEAMS = "teams"


class NotificationStatus(str, enum.Enum):
    """Outcome of one notification attempt, shown in the Settings → Notifications log so an
    admin can tell at a glance whether things are actually working."""

    SENT = "sent"
    # Channel is enabled but missing required config (e.g. no SMTP host) - logged instead of
    # raising, so a misconfigured channel never breaks the tracking poll that triggered it.
    SKIPPED = "skipped"
    FAILED = "failed"


class NotificationSettings(Base):
    """Admin-configured notification channels (Section 6.C) and daily-report schedule (Section
    9 Phase 4 / Section 7's "generates daily reports"). A singleton table - always exactly one
    row (id=1), created on demand by services/notification_service.get_settings() - rather than
    a list of channels, since the proposal describes exactly one email setup and one Teams
    webhook, not an arbitrary admin-managed list like TrackingSource."""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    smtp_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_port: Mapped[int] = mapped_column(Integer, nullable=False, default=587)
    smtp_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stored in plaintext for this project's scope (matching jwt_secret_key's dev-only
    # posture) - a production build would keep this in a secrets manager, not the DB.
    smtp_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    smtp_from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Comma-separated recipient list - kept as a single string rather than a related table
    # since there's no per-recipient state to track (no read receipts, preferences, etc.).
    email_recipients: Mapped[str | None] = mapped_column(String(500), nullable=True)

    teams_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    teams_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Daily report (Section 7 / Phase 4) - built and sent via whichever of the two channels
    # above are enabled, on the given UTC hour. See services/report_worker.py for how this is
    # actually scheduled (a lightweight once-per-hour check rather than reconfiguring
    # APScheduler every time this row changes).
    daily_report_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_report_hour_utc: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    # Date (YYYY-MM-DD) the daily report was last sent, so the hourly check can tell "already
    # sent today" apart from "haven't reached the hour yet" without a separate cron library.
    daily_report_last_sent_date: Mapped[str | None] = mapped_column(String(10), nullable=True)


class NotificationLog(Base):
    """Record of one notification attempt (event-triggered or the daily report), for the
    Settings → Notifications "recent activity" table. Append-only, like StatusEvent."""

    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[NotificationChannel] = mapped_column(Enum(NotificationChannel), nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(Enum(NotificationStatus), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    # Full message body actually sent (or attempted) - kept for troubleshooting, not shown in
    # the compact log table but available if needed.
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Which vessel/event this was about, if any (the daily report isn't tied to one vessel).
    vessel_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vessel_imo: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # Why it was skipped/failed, e.g. "SMTP host not configured" or an exception message.
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
