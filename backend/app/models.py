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
    app/routers/auth.py and app/cli.py. This holds regardless of *how* someone signs in
    (password or Microsoft, see AuthProvider) - every brand-new account starts as USER."""

    USER = "user"
    ADMIN = "admin"


class AuthProvider(str, enum.Enum):
    """How a user account authenticates. LOCAL accounts have a password; MICROSOFT accounts
    signed up via "Sign in with Microsoft" and have none (see User.password_hash). A LOCAL
    account can still *add* Microsoft sign-in later - see routers/auth.py's callback, which
    links by matching email rather than requiring a fresh account per provider."""

    LOCAL = "local"
    MICROSOFT = "microsoft"


class User(Base):
    """A login account. Registration always creates a USER; the first ADMIN is bootstrapped via
    the `promote-admin` CLI command, and every admin after that via the Settings → Users tab."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # bcrypt hash - the plaintext password is never stored. NULL for Microsoft-only accounts
    # that have never set a local password (see routers/auth.py's login(), which rejects a
    # password-login attempt against a NULL hash instead of crashing on it).
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.USER)
    auth_provider: Mapped[AuthProvider] = mapped_column(Enum(AuthProvider), nullable=False, default=AuthProvider.LOCAL)
    # Microsoft's own account id ("oid" from Graph /me), stored once a Microsoft sign-in has
    # linked to this row - lets us recognise the same Microsoft account on a later login even
    # if this was originally a LOCAL account (linked by matching email, see routers/auth.py).
    microsoft_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def microsoft_linked(self) -> bool:
        """Whether this account can currently sign in via Microsoft - true both for accounts
        that signed *up* via Microsoft and for LOCAL accounts that later linked one (see
        routers/auth.py's callback). Deliberately separate from `auth_provider`, which only
        records how the account was *originally* created and never changes after linking - a
        UserOut field consumers should use to decide "show the Microsoft badge", rather than
        `auth_provider`, which would stay "local" forever even after linking."""
        return self.microsoft_id is not None


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
    # Phase 6 (Section 7). Both cascade-delete with the vessel, same as `events` - an exception
    # or AI summary about a vessel that no longer exists has nothing to point at.
    exceptions: Mapped[list["VesselException"]] = relationship(
        back_populates="vessel", cascade="all, delete-orphan", order_by="VesselException.detected_at"
    )
    voyage_summary: Mapped["VoyageSummary | None"] = relationship(
        back_populates="vessel", cascade="all, delete-orphan", uselist=False
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
    # The ETA the source reported *at the time of this event* (Section 3.3 lists ETA among the
    # captured fields). NULL when the source didn't report one - e.g. a vessel with no
    # destination set, or an arrival event where an ETA is no longer meaningful.
    #
    # This is what makes Phase 6's delay detection real rather than guessed: "delayed" is
    # arithmetic against a source-reported ETA (see services/delay_detector.py), not an
    # inference. Until Phase 6 the app had no ETA anywhere, which is exactly why Section 6.E's
    # "Red = Delayed" colour and Figure 4's "Delayed" map legend sat unused - see
    # services/notification_service.py's original scope note.
    eta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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


class BookingStatus(str, enum.Enum):
    """The five stages of a container/booking's lifecycle (Section 4), sourced directly from the
    carrier's own booking record rather than AIS vessel-position data - unlike Vessel's EventType,
    there's no "derive from a raw report" ambiguity to resolve (see services/booking_status.py),
    because the carrier record already states which of these five stages applies. This is exactly
    what lets this module reliably distinguish loaded vs. discharged where vessel-position data
    alone cannot (Section 3.10)."""

    BOOKING_CONFIRMED = "booking_confirmed"
    LOADED = "loaded"
    IN_TRANSIT = "in_transit"
    DISCHARGED = "discharged"
    GATE_OUT = "gate_out"


class Booking(Base):
    """A tracked container/booking (Section 4) - the companion module to Vessel, deliberately
    "structured the same way as the vessel dashboard" per the proposal's own wording: its own
    fields plus a derived "current status" from the latest BookingEvent, the same
    flatten-latest-event approach as Vessel/StatusEvent (see services/presentation.py)."""

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Booking or container number, e.g. "ONEYBOOKG12345" / "TCLU7788990" - stored upper-cased
    # (see schemas.BookingCreate) so "tclu7788990" and "TCLU7788990" are treated as the same one.
    booking_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    shipping_line: Mapped[str] = mapped_column(String(80), nullable=False)
    port_of_loading: Mapped[str] = mapped_column(String(120), nullable=False)
    port_of_discharge: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Manual archive only (Section 3.8's pattern, mirrored here) - unlike Vessel there is no
    # auto-archive retention sweep for bookings: the proposal doesn't specify one for this module
    # (Section 3.7 is explicitly about the vessel dashboard), and "Gate Out" is already a clear,
    # final signal worth leaving visible rather than time-boxing away on a guessed retention period.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Same ordering/cascade contract as Vessel.events - see that model's comment.
    events: Mapped[list["BookingEvent"]] = relationship(
        back_populates="booking", cascade="all, delete-orphan", order_by="BookingEvent.occurred_at"
    )


class BookingEvent(Base):
    """One tracked update for a booking (Section 4) - e.g. "Loaded Shanghai". Append-only, the
    same contract as StatusEvent."""

    __tablename__ = "booking_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id"), nullable=False, index=True)
    status: Mapped[BookingStatus] = mapped_column(Enum(BookingStatus), nullable=False)
    # Where the cargo is right now per this report - a port name for most stages, or an "at sea"
    # description while IN_TRANSIT (see sources/mock_booking_adapter.py).
    current_location: Mapped[str] = mapped_column(String(160), nullable=False)
    # Human-readable "Last Event" text (Section 4), e.g. "Discharged Butterworth — 25 Jul 2026,
    # 07:55" - built by services/booking_status.py, the same pattern as StatusEvent.last_event_text.
    last_event_text: Mapped[str] = mapped_column(String(200), nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    booking: Mapped["Booking"] = relationship(back_populates="events")


class NotificationChannel(str, enum.Enum):
    """Email and Teams are Section 6.C's "at launch" channels; WhatsApp is the future
    enhancement the proposal's own Figure 5 labels "planned for phase 2 rollout", delivered here
    as part of Phase 6 (Section 9)."""

    EMAIL = "email"
    TEAMS = "teams"
    WHATSAPP = "whatsapp"


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

    # WhatsApp via Meta's WhatsApp Business Cloud API (Phase 6). Needs a phone-number id and a
    # bearer access token from the Meta app; recipients are comma-separated E.164 numbers.
    # Stored plaintext for this project's scope, same posture as smtp_password above.
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    whatsapp_access_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    whatsapp_recipients: Mapped[str | None] = mapped_column(String(500), nullable=True)

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


class ExceptionKind(str, enum.Enum):
    """The exception types Section 7's "AI Exception Alerts" bullet lists that this app can
    actually ground in data it holds.

    Detection is deliberately **rule-based, not model-inferred** (see
    services/exception_detector.py) - an alert that fires is one you can audit against a
    timestamp and a threshold. The AI layer in Phase 6 is the voyage *narrative*
    (services/ai_service.py), not the alerting.

    Section 7 also lists "route deviations", which is **not** implemented: detecting a deviation
    needs a planned route to deviate *from*, and nothing in the app (or in AIS-style position
    data - Section 3.10) supplies one. Rather than invent a plausible-looking signal, it's left
    out, consistent with how load/discharge categorisation was handled in 3.10.
    """

    # Past the source-reported ETA - either arrived late, or still not arrived. This is the one
    # that lights up Section 6.E's "Red = Delayed" colour.
    DELAYED = "delayed"
    # Sat AT_PORT longer than the configured threshold ("unusually long port stays").
    LONG_PORT_STAY = "long_port_stay"
    # Called at a port this vessel has never called at before and that isn't its destination
    # ("unexpected port calls"). "Unexpected" is defined precisely as *not seen in this vessel's
    # own recorded history*, so the claim is checkable rather than a vibe.
    UNEXPECTED_PORT_CALL = "unexpected_port_call"


class VesselException(Base):
    """One detected exception for a vessel (Section 7's "AI Exception Alerts"). Persisted rather
    than recomputed on the fly so that (a) each distinct exception notifies exactly once, and
    (b) the Exceptions page can show a history instead of only what's true this second."""

    __tablename__ = "vessel_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vessel_id: Mapped[int] = mapped_column(ForeignKey("vessels.id"), nullable=False, index=True)
    kind: Mapped[ExceptionKind] = mapped_column(Enum(ExceptionKind), nullable=False)
    # Human-readable explanation shown in the UI and sent in notifications, e.g.
    # "Arrived Pasir Gudang 6h 12m after the reported ETA".
    message: Mapped[str] = mapped_column(String(300), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Stable identity for "this same exception", so re-running detection on later ticks updates
    # nothing and re-notifies nobody. Built from vessel + kind + the specific event/port it's
    # about (see exception_detector.py), and unique across the table.
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)

    vessel: Mapped["Vessel"] = relationship(back_populates="exceptions")


class VoyageSummary(Base):
    """A cached AI-generated plain-language narrative of one vessel's voyage (Section 7's "AI
    Voyage Summary"; the proposal's Figure 3 sketches it as a panel on the vessel history page).

    Cached per-vessel rather than regenerated per view so repeat visits are instant and don't
    re-bill an API call. `source_event_count` records how many StatusEvents the summary was
    written from - the frontend uses it to show a "new events since this summary" hint, so a
    stale summary is visibly stale instead of quietly wrong.
    """

    __tablename__ = "voyage_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # One summary per vessel - regenerating overwrites in place rather than accumulating.
    vessel_id: Mapped[int] = mapped_column(ForeignKey("vessels.id"), unique=True, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    source_event_count: Mapped[int] = mapped_column(Integer, nullable=False)

    vessel: Mapped["Vessel"] = relationship(back_populates="voyage_summary")
