import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class EventType(str, enum.Enum):
    SAILING = "sailing"
    AT_PORT = "at_port"
    ETA_DESTINATION = "eta_destination"
    ARRIVED_DESTINATION = "arrived_destination"
    SAILED_FROM_DESTINATION = "sailed_from_destination"


class SourceKind(str, enum.Enum):
    VESSEL = "vessel"
    CONTAINER = "container"


class Vessel(Base):
    __tablename__ = "vessels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    imo_number: Mapped[str] = mapped_column(String(7), unique=True, index=True, nullable=False)
    destination_port: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["StatusEvent"]] = relationship(
        back_populates="vessel", cascade="all, delete-orphan", order_by="StatusEvent.occurred_at"
    )


class StatusEvent(Base):
    __tablename__ = "status_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vessel_id: Mapped[int] = mapped_column(ForeignKey("vessels.id"), nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    current_location: Mapped[str] = mapped_column(String(160), nullable=False)
    last_event_text: Mapped[str] = mapped_column(String(200), nullable=False)
    source_name: Mapped[str] = mapped_column(String(80), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vessel: Mapped["Vessel"] = relationship(back_populates="events")


class TrackingSource(Base):
    __tablename__ = "tracking_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    url: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[SourceKind] = mapped_column(Enum(SourceKind), nullable=False, default=SourceKind.VESSEL)
    adapter_key: Mapped[str] = mapped_column(String(40), nullable=False, default="mock")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
