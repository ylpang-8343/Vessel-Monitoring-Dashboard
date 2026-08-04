"""Pydantic request/response models - the API's input validation and output shape.

Kept separate from app/models.py (the DB schema) on purpose: these control exactly what a client
can send and what they get back (e.g. `UserOut` never includes `password_hash`), independent of
how the data happens to be stored.
"""

import re
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.models import EventType, UserRole


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


class VesselHistoryOut(BaseModel):
    """Response for GET /api/vessels/{imo}/history (Section 3.5) - the vessel plus its full
    timeline, oldest first."""

    vessel: VesselOut
    timeline: list[StatusEventOut]


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
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleUpdateRequest(BaseModel):
    """Payload for PATCH /api/users/{id}/role (promote/demote) - see routers/users.py for the
    last-admin guard applied when handling this."""

    role: UserRole
