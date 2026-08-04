"""Converts a Vessel ORM object into the flattened VesselOut shape the API/frontend use."""

from app.models import Vessel
from app.schemas import VesselOut


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
