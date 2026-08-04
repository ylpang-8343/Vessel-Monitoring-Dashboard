"""Implements the status decision flow from proposal Section 3.3a / Figure 1c:

    1. Source Report   -> reported position is a port call (arrived/departed) or open water
    2. Compare to Ports -> does the port match a known port at all
    3. Match to Destination -> does that port match the vessel's own configured destination
    4. Assign Status   -> Sailing/At Sea, At Port: [name], ETA to Destination,
                          Arrived at Destination, or Sailed from Destination

Destination-based statuses (ETA to Destination / Arrived at Destination / Sailed from
Destination) only ever apply when the vessel has a destination_port set (Section 3.1) -
this function simply never produces them otherwise.
"""

from app.models import EventType
from app.sources.base import RawReport


def _ports_match(a: str, b: str) -> bool:
    """Case/whitespace-insensitive port-name comparison, since a raw source report and a
    vessel's configured destination_port are just free-text strings that should still be
    treated as the same port even if capitalised differently."""
    return a.strip().casefold() == b.strip().casefold()


def derive_event_type(report: RawReport, destination_port: str | None) -> EventType:
    """Turn one raw tracking report into a dashboard-ready EventType, following the four-step
    flow described in the module docstring above."""
    has_destination = bool(destination_port)
    at_destination = has_destination and _ports_match(report.event_port, destination_port)

    if report.event_kind == "arrived":
        return EventType.ARRIVED_DESTINATION if at_destination else EventType.AT_PORT

    # departed
    if at_destination:
        return EventType.SAILED_FROM_DESTINATION
    if has_destination:
        # Underway with a destination set, but not departing *from* that destination itself -
        # i.e. this is progress toward it, hence "ETA to Destination" rather than plain sailing.
        return EventType.ETA_DESTINATION
    return EventType.SAILING


def format_last_event_text(report: RawReport) -> str:
    """Build the human-readable "Last Event" string shown on the dashboard (Section 3.4), e.g.
    "Arrived Shanghai — 20 Jul 2026, 08:00" or "Sailed Shanghai — 23 Jul 2026, 14:00"."""
    verb = "Arrived" if report.event_kind == "arrived" else "Sailed"
    timestamp = report.occurred_at.strftime("%d %b %Y, %H:%M")
    return f"{verb} {report.event_port} — {timestamp}"
