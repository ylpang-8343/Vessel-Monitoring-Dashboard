"""Container/Booking Tracking module (Section 4) - the companion to routers/vessels.py, same
shape: CRUD + listing with the 6.A search and a status filter, plus history and manual
archive/remove (Section 3.8's pattern, mirrored here - see models.Booking's docstring for why
there's no auto-archive sweep). Reachable by any logged-in user, not just admins, matching
vessels.py's gating (see app/main.py's include_router call)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Booking, BookingStatus
from app.schemas import BookingCreate, BookingHistoryOut, BookingOut
from app.services.presentation import to_booking_out

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.get("", response_model=list[BookingOut])
def list_bookings(
    q: str | None = None,
    archived: bool = False,
    status: BookingStatus | None = None,
    db: Session = Depends(get_db),
):
    """List bookings/containers for the Container/Booking table (Section 4).

    - `archived`: Active vs. Archived view, mirroring vessels' Active/Archived tabs.
    - `q`: free-text search (Section 6.A, extended to this module per Section 4's "can share the
      same search... patterns as the vessel dashboard") across booking number/shipping line/POL/POD.
    - `status`: filter chip - one of the five BookingStatus values (Section 4's own filter chips:
      All / Booking Confirmed / Loaded / In Transit / Discharged / Gate Out).

    `q` and `status` compose as a plain AND when both are given, matching list_vessels().
    """
    query = db.query(Booking)
    query = (
        query.filter(Booking.archived_at.isnot(None)) if archived else query.filter(Booking.archived_at.is_(None))
    )
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Booking.booking_number.ilike(like),
                Booking.shipping_line.ilike(like),
                Booking.port_of_loading.ilike(like),
                Booking.port_of_discharge.ilike(like),
            )
        )
    bookings = query.order_by(Booking.booking_number).all()
    out = [to_booking_out(b) for b in bookings]
    # Filtered on the derived latest-event status, same reasoning as list_vessels()'s status
    # filter - it isn't a column SQL can filter on directly.
    if status is not None:
        out = [b for b in out if b.last_event_status == status]
    return out


@router.post("", response_model=BookingOut, status_code=201)
def create_booking(payload: BookingCreate, db: Session = Depends(get_db)):
    """Register a new booking/container for tracking (Section 4). Rejects duplicate booking
    numbers, same as vessels' duplicate-IMO rejection; a booking starts with no events until the
    next poll picks it up."""
    existing = db.query(Booking).filter(Booking.booking_number == payload.booking_number).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Booking {payload.booking_number} is already registered")

    booking = Booking(
        booking_number=payload.booking_number,
        shipping_line=payload.shipping_line,
        port_of_loading=payload.port_of_loading,
        port_of_discharge=payload.port_of_discharge,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return to_booking_out(booking)


@router.get("/{booking_number}/history", response_model=BookingHistoryOut)
def get_booking_history(booking_number: str, db: Session = Depends(get_db)):
    """Full movement timeline for one booking (mirrors GET /api/vessels/{imo}/history)."""
    booking = db.query(Booking).filter(Booking.booking_number == booking_number.upper()).first()
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingHistoryOut(booking=to_booking_out(booking), timeline=list(booking.events))


@router.post("/{booking_number}/archive", response_model=BookingOut)
def archive_booking(booking_number: str, db: Session = Depends(get_db)):
    """Manually archive a booking (Section 3.8's pattern, mirrored here) - history stays fully
    intact and browsable afterwards."""
    booking = db.query(Booking).filter(Booking.booking_number == booking_number.upper()).first()
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.archived_at is not None:
        raise HTTPException(status_code=409, detail=f"Booking {booking_number} is already archived")

    booking.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)
    return to_booking_out(booking)


@router.delete("/{booking_number}", status_code=204)
def remove_booking(booking_number: str, db: Session = Depends(get_db)):
    """Permanently delete a booking and its entire history. Cascades via the ORM relationship in
    models.py, same as remove_vessel()."""
    booking = db.query(Booking).filter(Booking.booking_number == booking_number.upper()).first()
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    db.delete(booking)
    db.commit()
    return None
