"""Pydantic request/response models - the API's input validation and output shape.

Kept separate from app/models.py (the DB schema) on purpose: these control exactly what a client
can send and what they get back (e.g. `UserOut` never includes `password_hash`), independent of
how the data happens to be stored.
"""

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import (
    AuthProvider,
    BookingStatus,
    EventType,
    ExceptionKind,
    NotificationChannel,
    NotificationStatus,
    UserRole,
)


def validate_imo(value: str) -> str:
    """IMO numbers must be exactly 7 digits (Section 3.1). Shared by both the single-vessel
    schema below and the bulk-upload row validator in routers/bulk_upload.py."""
    value = value.strip()
    if not (value.isdigit() and len(value) == 7):
        raise ValueError("IMO number must be exactly 7 digits")
    return value


class VesselCreate(BaseModel):
    """Payload for registering a vessel (Section 3.1), used both for the single-vessel form and
    for each row imported via bulk upload."""

    name: str = Field(min_length=1, max_length=120)
    imo_number: str
    destination_port: str | None = None

    @field_validator("imo_number")
    @classmethod
    def check_imo(cls, v: str) -> str:
        return validate_imo(v)

    @field_validator("destination_port")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        # An empty string from a form field should behave the same as omitting the field
        # entirely - both mean "no destination set" (Section 3.1).
        if v is None:
            return None
        v = v.strip()
        return v or None


class StatusEventOut(BaseModel):
    """One row of a vessel's movement timeline (Section 3.5), as returned by the history
    endpoint."""

    id: int
    event_type: EventType
    current_location: str
    last_event_text: str
    source_name: str
    occurred_at: datetime
    recorded_at: datetime
    # The ETA the source reported at this event (Section 3.3); None when it didn't report one.
    eta: datetime | None = None

    # Lets Pydantic build this directly from a StatusEvent ORM object's attributes, instead of
    # requiring a dict.
    model_config = {"from_attributes": True}


class VesselOut(BaseModel):
    """A vessel as shown on the dashboard (Section 3.4) - its own fields plus a flattened view
    of its *latest* event (current_location, last_event_*, source_name), so the frontend doesn't
    need to separately fetch and find the most recent StatusEvent itself. Built by
    services/presentation.py's `to_vessel_out()`."""

    id: int
    name: str
    imo_number: str
    destination_port: str | None
    created_at: datetime
    archived_at: datetime | None = None
    # The next five fields are all None until the vessel's first tracking update arrives.
    current_location: str | None = None
    last_event_type: EventType | None = None
    last_event_text: str | None = None
    last_event_at: datetime | None = None
    source_name: str | None = None

    model_config = {"from_attributes": True}


class PredictedEtaOut(BaseModel):
    """Phase 6's predictive ETA (Section 7), with the evidence behind it so the UI can show
    *why* rather than presenting a bare timestamp - see services/predictive_eta.py."""

    predicted_arrival: datetime
    # How many of this vessel's own completed voyages on this route the estimate averages over.
    sample_size: int
    typical_duration_hours: float
    departed_from: str
    departed_at: datetime


class VesselHistoryOut(BaseModel):
    """Response for GET /api/vessels/{imo}/history (Section 3.5) - the vessel plus its full
    timeline, oldest first, plus the Phase 6 additions shown alongside it."""

    vessel: VesselOut
    timeline: list[StatusEventOut]
    # None when there's no basis for a prediction (no destination, not underway, or no
    # completed prior voyage on this route) - the UI omits the panel rather than guessing.
    predicted_eta: PredictedEtaOut | None = None
    # The most recent exceptions for this vessel, newest first - deliberately a slice, not the
    # full set. A long-serving vessel accumulates one exception per late voyage indefinitely,
    # and rendering all of them buries the timeline the page exists to show.
    exceptions: list["VesselExceptionOut"] = []
    # Total recorded for this vessel, so the UI can say "showing the most recent N of M" rather
    # than silently truncating.
    exception_count: int = 0


class VesselExceptionOut(BaseModel):
    """One detected exception (Section 7's "AI Exception Alerts"), for the Exceptions page and
    the vessel history panel. `vessel_name`/`vessel_imo` are flattened in so the standalone
    Exceptions list doesn't need a second lookup per row."""

    id: int
    vessel_name: str
    vessel_imo: str
    kind: ExceptionKind
    message: str
    detected_at: datetime

    model_config = {"from_attributes": True}


class VoyageSummaryOut(BaseModel):
    """A cached AI voyage summary (Section 7) plus enough metadata for the UI to say how current
    it is - `is_stale` is true once new tracking events have landed since it was written."""

    summary: str
    generated_at: datetime
    source_event_count: int
    is_stale: bool


class AiStatusOut(BaseModel):
    """Whether AI voyage summaries are usable on this deployment, so the frontend can hide the
    button rather than offering one that always fails (same posture as the Microsoft sign-in
    status endpoint)."""

    configured: bool


class BulkUploadRow(BaseModel):
    """One row from a bulk-upload preview (Section 3.2), before it's actually imported. Always
    shown to the user for review - see routers/bulk_upload.py for why this is never imported
    silently, especially for AI-extracted PDF rows."""

    row_number: int
    name: str | None = None
    imo_number: str | None = None
    destination_port: str | None = None
    status: str  # "ok" | "duplicate" | "invalid"
    message: str | None = None


class BulkUploadPreview(BaseModel):
    """Response for the bulk-upload preview endpoint: every parsed/extracted row, each already
    flagged ok/duplicate/invalid so the frontend can render it without re-deriving that itself."""

    rows: list[BulkUploadRow]


class BulkImportRequest(BaseModel):
    """Payload for actually importing rows after the user has reviewed/corrected the preview."""

    rows: list[VesselCreate]


class BulkImportResult(BaseModel):
    """What actually got imported vs. skipped (e.g. a duplicate IMO introduced between preview
    and import) - the import endpoint re-validates rather than trusting the preview blindly."""

    imported: list[VesselOut]
    skipped: list[BulkUploadRow]


class BookingCreate(BaseModel):
    """Payload for registering a booking/container for tracking (Section 4) - the companion of
    VesselCreate. All four fields are required, unlike a vessel's optional destination_port:
    a booking's whole purpose is tracking its journey between two known ports, so POL/POD aren't
    optional the way a vessel's free-standing destination is (Section 3.1)."""

    booking_number: str = Field(min_length=1, max_length=30)
    shipping_line: str = Field(min_length=1, max_length=80)
    port_of_loading: str = Field(min_length=1, max_length=120)
    port_of_discharge: str = Field(min_length=1, max_length=120)

    @field_validator("booking_number")
    @classmethod
    def normalize_booking_number(cls, v: str) -> str:
        # Upper-cased and trimmed so e.g. "tclu7788990" and "TCLU7788990" collide as the same
        # booking on the uniqueness check (routers/bookings.py), matching how container/booking
        # numbers are conventionally written (Section 4's own examples are all upper-case).
        v = v.strip().upper()
        if not v:
            raise ValueError("Booking/container number is required")
        return v


class BookingEventOut(BaseModel):
    """One row of a booking's movement timeline (Section 4), mirroring StatusEventOut."""

    id: int
    status: BookingStatus
    current_location: str
    last_event_text: str
    source_name: str
    occurred_at: datetime
    recorded_at: datetime

    model_config = {"from_attributes": True}


class BookingOut(BaseModel):
    """A booking/container as shown on the Container/Booking table (Section 4) - its own fields
    plus a flattened view of its *latest* event, mirroring VesselOut. Built by
    services/presentation.py's `to_booking_out()`."""

    id: int
    booking_number: str
    shipping_line: str
    port_of_loading: str
    port_of_discharge: str
    created_at: datetime
    archived_at: datetime | None = None
    current_location: str | None = None
    last_event_status: BookingStatus | None = None
    last_event_text: str | None = None
    last_event_at: datetime | None = None
    source_name: str | None = None

    model_config = {"from_attributes": True}


class BookingHistoryOut(BaseModel):
    """Response for GET /api/bookings/{booking_number}/history - mirrors VesselHistoryOut."""

    booking: BookingOut
    timeline: list[BookingEventOut]


class TrackingSourceOut(BaseModel):
    """A tracking source as shown on Settings → Tracking Sources (Section 3.9)."""

    id: int
    name: str
    url: str
    kind: str
    adapter_key: str
    enabled: bool

    model_config = {"from_attributes": True}


class TrackingSourceCreate(BaseModel):
    """Payload for adding a new tracking source. New sources default to a non-functional
    "unavailable" adapter and disabled - only the seeded "mock" source actually polls (Section
    3.9's note about no real credentials being available yet)."""

    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=255)
    kind: str = "vessel"
    adapter_key: str = "unavailable"
    enabled: bool = False


class TrackingSourceUpdate(BaseModel):
    """Payload for editing a tracking source - every field optional so a PATCH can change just
    one of them (e.g. only toggling `enabled`)."""

    name: str | None = None
    url: str | None = None
    kind: str | None = None
    adapter_key: str | None = None
    enabled: bool | None = None


def validate_password_complexity(value: str) -> str:
    """Enforced rule: at least 8 characters, one uppercase, one lowercase, one symbol. Mirrored
    client-side in frontend/app/register/page.tsx's live checklist, but this is the source of
    truth - the API re-validates regardless of what the frontend already checked."""
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", value):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", value):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"[^A-Za-z0-9]", value):
        raise ValueError("Password must contain at least one symbol")
    return value


class UserRegister(BaseModel):
    """Registration payload. Always results in a `user`-role account - there is no field here
    (or anywhere in the API) that can request `admin` on signup."""

    email: EmailStr
    password: str
    confirm_password: str

    @field_validator("password")
    @classmethod
    def check_password_complexity(cls, v: str) -> str:
        return validate_password_complexity(v)

    @model_validator(mode="after")
    def check_passwords_match(self) -> "UserRegister":
        # Runs after both fields are individually validated, so it can compare them against
        # each other (a single-field validator can't see confirm_password).
        if self.password != self.confirm_password:
            raise ValueError("Password and confirmation do not match")
        return self


class UserLogin(BaseModel):
    """Login payload - no complexity re-validation here, since an existing password may predate
    a rule change; only registration enforces the complexity rule."""

    email: EmailStr
    password: str


class UserOut(BaseModel):
    """A user as returned by the API - deliberately excludes `password_hash`."""

    id: int
    email: str
    role: UserRole
    # How the account was originally created - not necessarily how it can *still* sign in
    # today, see `microsoft_linked` below (a LOCAL account can link Microsoft sign-in later).
    auth_provider: AuthProvider
    # Whether Microsoft sign-in currently works for this account (true for both Microsoft-
    # native signups and LOCAL accounts that later linked one) - this, not `auth_provider`, is
    # what the Settings -> Users "Microsoft" badge is based on.
    microsoft_linked: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleUpdateRequest(BaseModel):
    """Payload for PATCH /api/users/{id}/role (promote/demote) - see routers/users.py for the
    last-admin guard applied when handling this."""

    role: UserRole


class MicrosoftStatusOut(BaseModel):
    """Response for GET /api/auth/microsoft/status - whether "Sign in with Microsoft" is
    actually configured on this deployment, so the frontend knows whether to show the button."""

    configured: bool


class NotificationSettingsOut(BaseModel):
    """Notification/report configuration as shown on Settings → Notifications (Section 6.C).

    Deliberately omits `smtp_password` - the frontend never needs it back, only whether one is
    already set (see `smtp_password_set`), so a saved password can never round-trip into a
    browser response.
    """

    email_enabled: bool
    smtp_host: str | None
    smtp_port: int
    smtp_username: str | None
    smtp_password_set: bool
    smtp_from_address: str | None
    email_recipients: str | None

    teams_enabled: bool
    teams_webhook_url: str | None

    # Like smtp_password, the access token never round-trips back to the browser - only
    # whether one is stored (see `whatsapp_access_token_set`).
    whatsapp_enabled: bool
    whatsapp_phone_number_id: str | None
    whatsapp_access_token_set: bool
    whatsapp_recipients: str | None

    daily_report_enabled: bool
    daily_report_hour_utc: int
    daily_report_last_sent_date: str | None


class NotificationSettingsUpdate(BaseModel):
    """Payload for PATCH /api/notifications/settings - every field optional so the Email and
    Teams cards on the frontend can each save independently without clobbering the other's
    fields. `smtp_password` is only updated when provided (omitted/None leaves the existing
    stored password untouched, so re-saving the Email card doesn't force re-entering it)."""

    email_enabled: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_address: str | None = None
    email_recipients: str | None = None

    teams_enabled: bool | None = None
    teams_webhook_url: str | None = None

    # `whatsapp_access_token` follows the same only-updated-when-provided rule as smtp_password.
    whatsapp_enabled: bool | None = None
    whatsapp_phone_number_id: str | None = None
    whatsapp_access_token: str | None = None
    whatsapp_recipients: str | None = None

    daily_report_enabled: bool | None = None
    daily_report_hour_utc: int | None = Field(default=None, ge=0, le=23)


class NotificationLogOut(BaseModel):
    """One row of the "recent notifications" table - lets an admin verify a channel is actually
    working (or see exactly why it isn't) without digging through server logs."""

    id: int
    channel: NotificationChannel
    status: NotificationStatus
    subject: str
    vessel_name: str | None
    vessel_imo: str | None
    detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportSummaryOut(BaseModel):
    """Data behind the Reports page (Section 7 / Phase 4) and its Excel/PDF exports - the same
    three vessel categories, computed once and reused for the on-screen view and both file
    formats. "Delayed vessels" (the proposal's fourth category) is intentionally not included -
    see services/report_service.py's module docstring for why."""

    active: list[VesselOut]
    eta_to_destination: list[VesselOut]
    arrived_at_destination: list[VesselOut]
    generated_at: datetime
