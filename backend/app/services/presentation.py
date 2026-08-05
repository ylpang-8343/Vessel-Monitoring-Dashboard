"""Converts ORM objects into the flattened *Out shapes the API/frontend use - one function per
entity that has a "current status derived from its latest event" pattern (Vessel/StatusEvent,
Booking/BookingEvent)."""

from app.models import Booking, Vessel
from app.schemas import BookingOut, VesselOut


def to_vessel_out(vessel: Vessel) -> VesselOut:
    """Build a VesselOut, folding in the vessel's *latest* StatusEvent (if any) as its
    current_location/last_event_*/source_name fields (Section 3.6 - "the dashboard always
    surfaces the most recent status per vessel"). `vessel.events` is ordered oldest-first (see
    the relationship definition in models.py), so the latest one is simply the last element."""
    latest = vessel.events[-1] if vessel.events else None
    return VesselOut(
        id=vessel.id,
        name=vessel.name,
        imo_number=vessel.imo_number,
        destination_port=vessel.destination_port,
        created_at=vessel.created_at,
        archived_at=vessel.archived_at,
        current_location=latest.current_location if latest else None,
        last_event_type=latest.event_type if latest else None,
        last_event_text=latest.last_event_text if latest else None,
        last_event_at=latest.occurred_at if latest else None,
        source_name=latest.source_name if latest else None,
    )


def to_booking_out(booking: Booking) -> BookingOut:
    """Build a BookingOut, folding in the booking's *latest* BookingEvent (if any) - the same
    flatten-latest-event pattern as to_vessel_out() above, applied to the Container/Booking
    Tracking module (Section 4)."""
    latest = booking.events[-1] if booking.events else None
    return BookingOut(
        id=booking.id,
        booking_number=booking.booking_number,
        shipping_line=booking.shipping_line,
        port_of_loading=booking.port_of_loading,
        port_of_discharge=booking.port_of_discharge,
        created_at=booking.created_at,
        archived_at=booking.archived_at,
        current_location=latest.current_location if latest else None,
        last_event_status=latest.status if latest else None,
        last_event_text=latest.last_event_text if latest else None,
        last_event_at=latest.occurred_at if latest else None,
        source_name=latest.source_name if latest else None,
    )
