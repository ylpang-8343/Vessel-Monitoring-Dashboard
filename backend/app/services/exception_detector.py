"""AI Exception Alerts (Section 7): flags delays, unusually long port stays, and unexpected port
calls, from data the app actually holds.

**Detection here is rule-based, not model-inferred, and that is a deliberate choice.** An alert
is a claim that something is wrong, and the useful property of such a claim is that a user can
check it: "arrived 6h 12m after the reported ETA of 14:00" is auditable against the timeline;
"the model thought this looked late" is not. Rules also cost nothing per tick and never fire
differently on identical inputs. The AI layer Phase 6 adds is the voyage *narrative*
(services/ai_service.py) - explaining a vessel's history in plain language, which is a genuine
language task - not the alerting, which is arithmetic.

Section 7 also lists **route deviations**, which is deliberately not implemented: detecting a
deviation requires a planned route to compare against, and neither the app nor AIS-style position
reporting supplies one (the same reasoning Section 3.10 applies to load/discharge). Inventing a
"deviation" signal from port calls alone would be exactly the guesswork 3.10 argues against.

Each detected exception is persisted once, keyed by a dedupe key built from the vessel, the kind,
and the specific event it concerns (see models.VesselException) - so running detection on every
tracking-poll tick is idempotent and nobody gets re-notified about the same thing.
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import EventType, ExceptionKind, StatusEvent, Vessel, VesselException
from app.services.timeutil import as_naive_utc, utc_now_naive

logger = logging.getLogger("exception_detector")


def _format_duration(delta: timedelta) -> str:
    """Render a duration the way the alert messages read best - "6h 12m", "3d 4h", "45m".
    Rounded to the two largest units, since alert text doesn't benefit from seconds."""
    total_minutes = int(delta.total_seconds() // 60)
    days, remainder = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _latest_reported_eta(events: list[StatusEvent], before_index: int) -> StatusEvent | None:
    """The most recent event at or before `before_index` that carried a source-reported ETA.

    Delay is measured against the *latest* ETA the source gave, not the first - a source that
    revises its ETA is providing better information, and holding a vessel to a superseded
    estimate would flag delays that the source itself no longer claims.
    """
    for event in reversed(events[: before_index + 1]):
        if event.eta is not None:
            return event
    return None


def _detect_delay(vessel: Vessel) -> tuple[ExceptionKind, str, str] | None:
    """Delayed = the vessel missed the ETA its source reported, either by arriving late or by
    still being underway past it. Returns (kind, message, dedupe_key) or None.

    Needs a source-reported ETA to compare against; a vessel whose source never reported one
    (including every vessel with no destination set) can't be late in any checkable sense.
    """
    if not vessel.events:
        return None

    grace = timedelta(minutes=settings.delay_threshold_minutes)
    latest_index = len(vessel.events) - 1
    latest = vessel.events[latest_index]

    if latest.event_type == EventType.ARRIVED_DESTINATION:
        # Arrived - was it later than the last ETA reported before the arrival?
        eta_event = _latest_reported_eta(vessel.events, latest_index - 1)
        if eta_event is None:
            return None
        lateness = as_naive_utc(latest.occurred_at) - as_naive_utc(eta_event.eta)
        if lateness <= grace:
            return None
        message = (
            f"Arrived at {vessel.destination_port} {_format_duration(lateness)} after the "
            f"reported ETA of {as_naive_utc(eta_event.eta).strftime('%d %b %Y, %H:%M')} UTC"
        )
        # Keyed on the arrival event: one alert per late arrival, re-checked harmlessly forever.
        return ExceptionKind.DELAYED, message, f"{vessel.id}:delayed:{latest.id}"

    if latest.event_type == EventType.ETA_DESTINATION:
        # Still underway - overdue if the reported ETA has already passed.
        eta_event = _latest_reported_eta(vessel.events, latest_index)
        if eta_event is None:
            return None
        overdue_by = utc_now_naive() - as_naive_utc(eta_event.eta)
        if overdue_by <= grace:
            return None
        message = (
            f"Still en route to {vessel.destination_port}, {_format_duration(overdue_by)} past "
            f"the reported ETA of {as_naive_utc(eta_event.eta).strftime('%d %b %Y, %H:%M')} UTC"
        )
        # Keyed on the ETA-bearing event rather than "now", so an overdue vessel raises one
        # alert for that missed ETA instead of a fresh one on every poll tick.
        return ExceptionKind.DELAYED, message, f"{vessel.id}:delayed:overdue:{eta_event.id}"

    return None


def _detect_long_port_stay(vessel: Vessel) -> tuple[ExceptionKind, str, str] | None:
    """Unusually long port stay = currently AT_PORT and has been since longer ago than the
    configured threshold. Measured from the arrival event's own timestamp, so it reflects how
    long the vessel has actually been there rather than how long we've been watching."""
    if not vessel.events:
        return None
    latest = vessel.events[-1]
    if latest.event_type != EventType.AT_PORT:
        return None

    stayed = utc_now_naive() - as_naive_utc(latest.occurred_at)
    if stayed <= timedelta(hours=settings.long_port_stay_hours):
        return None

    message = (
        f"At {latest.current_location} for {_format_duration(stayed)} - longer than the "
        f"{settings.long_port_stay_hours}h threshold"
    )
    return ExceptionKind.LONG_PORT_STAY, message, f"{vessel.id}:long_port_stay:{latest.id}"


def _detect_unexpected_port_call(vessel: Vessel) -> tuple[ExceptionKind, str, str] | None:
    """Unexpected port call = the vessel just arrived somewhere it has never called at before
    and that isn't its destination.

    "Unexpected" is given a precise, checkable meaning here - *absent from this vessel's own
    recorded history* - rather than being left to judgement. That does mean a vessel's very
    first port call can't be unexpected (there's no history to be absent from), which is the
    correct behaviour: with one data point there is no pattern to deviate from.
    """
    if len(vessel.events) < 2:
        return None
    latest = vessel.events[-1]
    if latest.event_type != EventType.AT_PORT:
        return None

    port = latest.current_location
    if vessel.destination_port and port.strip().casefold() == vessel.destination_port.strip().casefold():
        return None

    seen_before = {
        event.current_location.strip().casefold()
        for event in vessel.events[:-1]
        if event.event_type in (EventType.AT_PORT, EventType.ARRIVED_DESTINATION)
    }
    if port.strip().casefold() in seen_before:
        return None

    message = f"Called at {port}, which is not {vessel.name}'s destination and not in its recorded history"
    return ExceptionKind.UNEXPECTED_PORT_CALL, message, f"{vessel.id}:unexpected_port_call:{latest.id}"


# Every detector takes a Vessel and returns (kind, message, dedupe_key) or None. Adding a new
# exception type means writing one function and appending it here.
_DETECTORS = (_detect_delay, _detect_long_port_stay, _detect_unexpected_port_call)


def detect_for_vessel(db: Session, vessel: Vessel) -> list[VesselException]:
    """Run every detector against one vessel and persist any exception not already recorded.
    Returns only the *newly created* rows, so callers can notify about exactly those."""
    created: list[VesselException] = []

    for detector in _DETECTORS:
        result = detector(vessel)
        if result is None:
            continue
        kind, message, dedupe_key = result

        already = db.query(VesselException).filter(VesselException.dedupe_key == dedupe_key).first()
        if already is not None:
            continue

        exception = VesselException(vessel_id=vessel.id, kind=kind, message=message, dedupe_key=dedupe_key)
        db.add(exception)
        created.append(exception)

    if created:
        db.commit()
    return created


def run_exception_sweep(db: Session) -> list[VesselException]:
    """Run detection across every active vessel. Called on each tracking-poll tick (see
    services/tracking_worker.py) - archived vessels are excluded, since an exception about a
    vessel nobody is monitoring anymore isn't actionable."""
    vessels = db.query(Vessel).filter(Vessel.archived_at.is_(None)).all()
    created: list[VesselException] = []
    for vessel in vessels:
        try:
            created.extend(detect_for_vessel(db, vessel))
        except Exception:
            # One vessel's bad data must not stop the sweep for every other vessel.
            logger.exception("exception detection failed for vessel %s", vessel.imo_number)
    return created
