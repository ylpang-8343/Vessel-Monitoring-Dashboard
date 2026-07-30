from app.models import Vessel
from app.schemas import VesselOut


def to_vessel_out(vessel: Vessel) -> VesselOut:
    latest = vessel.events[-1] if vessel.events else None
    return VesselOut(
        id=vessel.id,
        name=vessel.name,
        imo_number=vessel.imo_number,
        destination_port=vessel.destination_port,
        created_at=vessel.created_at,
        current_location=latest.current_location if latest else None,
        last_event_type=latest.event_type if latest else None,
        last_event_text=latest.last_event_text if latest else None,
        last_event_at=latest.occurred_at if latest else None,
        source_name=latest.source_name if latest else None,
    )
