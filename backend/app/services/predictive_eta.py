"""AI Predictive ETA (Section 7), grounded in each vessel's own recorded history.

The proposal describes this as using "vessel speed, route, and historical data to refine arrival
predictions beyond the source website's ETA". Of those three inputs this app only genuinely has
the third: AIS-style position reports as modelled here carry no speed and no route geometry (the
same data-availability limit Section 3.10 describes for load/discharge). So the prediction is
built purely from **completed voyages this vessel has actually made between the same two ports**:

    predicted arrival = departure time of the current voyage
                      + median duration of that vessel's previous origin -> destination runs

Median rather than mean, so one freak voyage (a long weather hold, a mid-voyage archive/restore)
doesn't drag every future prediction with it.

This is deliberately *not* a model call. A number presented next to a source-reported ETA needs
to be reproducible and explainable - "median of your last N runs on this route" is both, and a
user can check it against the timeline. `sample_size` is returned alongside so the UI can show
how much history is behind the number rather than presenting one voyage's duration as a forecast.

Returns None rather than guessing whenever the history isn't there - a vessel on a route it has
never completed before has no basis for a prediction, and saying so is more useful than inventing
one (see services/notification_service.py's module docstring for the same posture applied to
delay alerts before Phase 6 made them groundable).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

from app.models import EventType, StatusEvent, Vessel

# A single prior voyage is a data point, not a distribution - but it's still strictly better
# information than nothing, and `sample_size` lets the UI caveat it. Below 1 there's no
# prediction to make at all.
MIN_SAMPLE_SIZE = 1


@dataclass
class PredictedEta:
    """A predicted arrival time plus the evidence behind it, so callers can show *why*."""

    predicted_arrival: datetime
    # How many completed prior voyages on this route the median was taken over.
    sample_size: int
    # The median transit duration those voyages took.
    typical_duration: timedelta
    # Where the current voyage started, for the explanatory text.
    departed_from: str
    departed_at: datetime


def _completed_transits(events: list[StatusEvent], destination: str) -> list[tuple[str, timedelta]]:
    """Walk a vessel's timeline and pull out every completed departure -> arrival-at-destination
    leg, as (origin port, duration) pairs.

    A "leg" is a departure event followed later by an ARRIVED_DESTINATION event with no
    intervening arrival at the destination. Legs still in progress (a departure with no matching
    arrival yet) are skipped - only finished voyages inform the median.
    """
    transits: list[tuple[str, timedelta]] = []
    open_departure: StatusEvent | None = None

    for event in events:
        if event.event_type == EventType.ETA_DESTINATION:
            # Underway toward the destination - this starts (or restarts) a leg.
            open_departure = event
        elif event.event_type == EventType.ARRIVED_DESTINATION and open_departure is not None:
            duration = event.occurred_at - open_departure.occurred_at
            # Guard against clock skew or out-of-order source reports producing a negative or
            # zero-length "voyage", which would poison the median.
            if duration > timedelta(0):
                transits.append((open_departure.current_location, duration))
            open_departure = None

    return transits


def predict_arrival(vessel: Vessel) -> PredictedEta | None:
    """Predict when `vessel` will arrive at its configured destination, from the median duration
    of its own previously completed voyages there. None when there's no basis for a prediction:
    no destination set, not currently underway toward it, or no completed prior voyage.

    `vessel.events` is ordered oldest-first (see models.py), which is what lets the leg-pairing
    walk in `_completed_transits` work in a single pass.
    """
    if not vessel.destination_port or not vessel.events:
        return None

    latest = vessel.events[-1]
    # Only meaningful while actually en route. A vessel sitting at port or already arrived
    # doesn't need an arrival predicted for it.
    if latest.event_type != EventType.ETA_DESTINATION:
        return None

    # Exclude the in-progress leg itself: it's the thing being predicted, not evidence for it.
    completed = _completed_transits(vessel.events[:-1], vessel.destination_port)
    if len(completed) < MIN_SAMPLE_SIZE:
        return None

    typical = median(duration for _, duration in completed)
    return PredictedEta(
        predicted_arrival=latest.occurred_at + typical,
        sample_size=len(completed),
        typical_duration=typical,
        departed_from=latest.current_location,
        departed_at=latest.occurred_at,
    )
