"""SQLAlchemy ORM models - the database schema.

Tables are created automatically at backend startup via `Base.metadata.create_all()`
(see app/main.py's `lifespan`). That call only *adds* new tables/columns that don't exist yet;
it never alters an existing table, so a schema change on a database that already has the old
shape needs a volume reset in dev (see README.md) or a real migration tool in production.
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
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
