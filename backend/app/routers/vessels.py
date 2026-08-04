"""Core vessel CRUD + listing (Sections 3.1, 3.4, 3.7's manual side via archive, 3.8), plus the
6.A search and 6.D status-filter query params backing the dashboard."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EventType, Vessel
from app.schemas import VesselCreate, VesselOut
from app.services.presentation import to_vessel_out

router = APIRouter(prefix="/api/vessels", tags=["vessels"])


@router.get("", response_model=list[VesselOut])
def list_vessels(
    q: str | None = None,
    archived: bool = False,
    status: EventType | None = None,
    db: Session = Depends(get_db),
):
    """List vessels for the dashboard.

    - `archived`: Active tab (default) vs. Archived tab (Section 3.7/3.8) - these are always
      mutually exclusive views, never combined.
    - `q`: free-text search (Section 6.A) across name/IMO/destination, applied in SQL.
    - `status`: filter chip (Section 6.D) - applied in Python after resolving each vessel's
      latest event, since "current status" isn't a column that exists to filter on directly.

    `q` and `status` compose as a plain AND when both are given.
    """
    query = db.query(Vessel)
    query = query.filter(Vessel.archived_at.isnot(None)) if archived else query.filter(Vessel.archived_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Vessel.name.ilike(like),
                Vessel.imo_number.ilike(like),
                Vessel.destination_port.ilike(like),
            )
        )
    vessels = query.order_by(Vessel.name).all()
    out = [to_vessel_out(v) for v in vessels]
    # Filtered on the derived latest-event status (6.D filter chips), which only exists after
    # to_vessel_out() resolves each vessel's last event - not a column SQL can filter on directly.
    if status is not None:
        out = [v for v in out if v.last_event_type == status]
    return out


@router.post("", response_model=VesselOut, status_code=201)
def create_vessel(payload: VesselCreate, db: Session = Depends(get_db)):
    """Register a new vessel (Section 3.1). Rejects duplicate IMO numbers; a vessel starts with
    no events at all, so it shows "Awaiting first tracking update…" until the next poll."""
    existing = db.query(Vessel).filter(Vessel.imo_number == payload.imo_number).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"IMO {payload.imo_number} is already registered")

    vessel = Vessel(
        name=payload.name,
        imo_number=payload.imo_number,
        destination_port=payload.destination_port,
    )
    db.add(vessel)
    db.commit()
    db.refresh(vessel)
    return to_vessel_out(vessel)


@router.post("/{imo_number}/archive", response_model=VesselOut)
def archive_vessel(imo_number: str, db: Session = Depends(get_db)):
    """Manually archive a vessel (Section 3.8) - the same one-way action the Section 3.7
    retention sweep performs automatically, just triggered by a user instead of the scheduler.
    History stays fully intact and browsable afterwards."""
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    if vessel.archived_at is not None:
        raise HTTPException(status_code=409, detail=f"Vessel {imo_number} is already archived")

    vessel.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vessel)
    return to_vessel_out(vessel)


@router.delete("/{imo_number}", status_code=204)
def remove_vessel(imo_number: str, db: Session = Depends(get_db)):
    """Permanently delete a vessel and its entire history (Section 3.8's "remove" option, as
    opposed to "archive" which keeps history). Cascades via the ORM relationship in
    models.py (`cascade="all, delete-orphan"`), so no orphaned StatusEvent rows are left behind."""
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")

    db.delete(vessel)
    db.commit()
    return None
