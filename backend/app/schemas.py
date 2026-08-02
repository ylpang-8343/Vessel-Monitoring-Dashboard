from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models import EventType


def validate_imo(value: str) -> str:
    value = value.strip()
    if not (value.isdigit() and len(value) == 7):
        raise ValueError("IMO number must be exactly 7 digits")
    return value


class VesselCreate(BaseModel):
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
        if v is None:
            return None
        v = v.strip()
        return v or None


class StatusEventOut(BaseModel):
    id: int
    event_type: EventType
    current_location: str
    last_event_text: str
    source_name: str
    occurred_at: datetime
    recorded_at: datetime

    model_config = {"from_attributes": True}


class VesselOut(BaseModel):
    id: int
    name: str
    imo_number: str
    destination_port: str | None
    created_at: datetime
    archived_at: datetime | None = None
    current_location: str | None = None
    last_event_type: EventType | None = None
    last_event_text: str | None = None
    last_event_at: datetime | None = None
    source_name: str | None = None

    model_config = {"from_attributes": True}


class VesselHistoryOut(BaseModel):
    vessel: VesselOut
    timeline: list[StatusEventOut]


class BulkUploadRow(BaseModel):
    row_number: int
    name: str | None = None
    imo_number: str | None = None
    destination_port: str | None = None
    status: str  # "ok" | "duplicate" | "invalid"
    message: str | None = None


class BulkUploadPreview(BaseModel):
    rows: list[BulkUploadRow]


class BulkImportRequest(BaseModel):
    rows: list[VesselCreate]


class BulkImportResult(BaseModel):
    imported: list[VesselOut]
    skipped: list[BulkUploadRow]


class TrackingSourceOut(BaseModel):
    id: int
    name: str
    url: str
    kind: str
    adapter_key: str
    enabled: bool

    model_config = {"from_attributes": True}


class TrackingSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    url: str = Field(min_length=1, max_length=255)
    kind: str = "vessel"
    adapter_key: str = "unavailable"
    enabled: bool = False


class TrackingSourceUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    kind: str | None = None
    adapter_key: str | None = None
    enabled: bool | None = None
