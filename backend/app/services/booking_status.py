"""Formats the human-readable "Last Event" text for a booking/container update (Section 4),
mirroring services/status_engine.py's format_last_event_text for vessels.

There's no equivalent of that module's `derive_event_type` here: a vessel's raw report only says
"arrived"/"departed" at some port, so the status engine has to *infer* whether that counts as
"ETA to Destination" vs. plain "Sailing" by comparing against the vessel's own configured
destination (Section 3.3a). A booking's raw report already states its lifecycle stage directly
(BookingStatus - see models.py's docstring on it) - carrier records are that much more precise
than AIS position data (Section 3.10) - so there's nothing left to derive, only to format.
"""

from app.models import BookingStatus
from app.sources.booking_base import RawBookingReport

# Verb shown at the start of the "Last Event" text for each stage - matches the proposal's own
# Figure 3a examples ("Loaded Shanghai — …", "Discharged Butterworth — …") and Section 8.1's
# "Departed Qingdao — …" for a booking that's in transit.
_VERBS: dict[BookingStatus, str] = {
    BookingStatus.BOOKING_CONFIRMED: "Booking Confirmed",
    BookingStatus.LOADED: "Loaded",
    BookingStatus.IN_TRANSIT: "Departed",
    BookingStatus.DISCHARGED: "Discharged",
    BookingStatus.GATE_OUT: "Gate Out",
}


# Which of the booking's two fixed ports (Section 4's POL/POD columns) each stage happened at -
# the early stages are POL-side events, the later two are POD-side.
_PORT_SIDE: dict[BookingStatus, str] = {
    BookingStatus.BOOKING_CONFIRMED: "loading",
    BookingStatus.LOADED: "loading",
    BookingStatus.IN_TRANSIT: "loading",  # "Departed <POL>" - see _VERBS
    BookingStatus.DISCHARGED: "discharge",
    BookingStatus.GATE_OUT: "discharge",
}


def format_last_event_text(report: RawBookingReport, port_of_loading: str, port_of_discharge: str) -> str:
    """Build the "Last Event" string shown in the Container/Booking table (Section 4), e.g.
    "Loaded Shanghai — 24 Jul 2026, 09:40" or "Discharged Butterworth — 25 Jul 2026, 07:55".
    Takes both of the booking's fixed ports rather than a single `event_port`, since
    RawBookingReport only carries the cargo's *current* location (which, for IN_TRANSIT, is an
    "at sea" description, not a port name) - the port actually named in the text is picked here
    based on which stage this report is for (see _PORT_SIDE)."""
    verb = _VERBS[report.status]
    port = port_of_loading if _PORT_SIDE[report.status] == "loading" else port_of_discharge
    timestamp = report.occurred_at.strftime("%d %b %Y, %H:%M")
    return f"{verb} {port} — {timestamp}"
