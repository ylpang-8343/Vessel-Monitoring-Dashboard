"""Simulated tracking source.

Advances each vessel through a simple, repeating voyage cycle by one step every time
poll() is called (i.e. once per tracking-worker tick). This exercises the full
ingest -> status engine -> StatusEvent -> dashboard pipeline end-to-end without
depending on real MarineTraffic/VesselFinder/Polestar GMDA access, which the
proposal notes requires credentials/API terms not yet available (Section 10).

Swap this out for a real scraper/API-backed adapter later via the same
TrackingSourceAdapter interface -- nothing else in the app needs to change.

Vessels with a destination *dwell* at "Arrived at Destination" for DWELL_TICKS polls
(no new event emitted) before departing again. Without this, a vessel would depart on
the very next tick after arriving, so its latest event would never stay
ARRIVED_DESTINATION across ticks - which would make the Section 3.7 auto-archive
retention sweep (run_archive_sweep, checked every tick in tracking_worker.py) unable to
ever find a vessel that's actually "sitting" arrived, since the poll that runs just
before the sweep on every tick would always have already advanced it past that state.
"""

import random
from datetime import datetime, timezone

from app.sources.base import RawReport, TrackingSourceAdapter

# Every location string these simulated voyages can produce also has a real-world lat/lng in
# frontend/lib/portCoordinates.ts, so vessels running through this mock data show up correctly
# positioned on the Map View (Section 6.B) - not just plausible-looking text.
ORIGIN_PORTS = ["Qingdao", "Shanghai", "Xiamen", "Ningbo"]
SEA_REGIONS = ["South China Sea", "Strait of Malacca", "Singapore Strait", "Andaman Sea"]
WAYPOINT_PORTS = ["Singapore Anchorage", "Port Klang South"]
# How many poll ticks a vessel stays at ARRIVED_DESTINATION before departing again - see the
# module docstring for why this needs to be >0.
DWELL_TICKS = 2


class MockAdapter(TrackingSourceAdapter):
    """Stand-in TrackingSourceAdapter that fabricates a repeating voyage cycle per vessel
    instead of calling a real tracking website. See the module docstring for why this exists
    and how the dwell mechanic works."""

    adapter_key = "mock"

    def __init__(self, source_name: str = "Mock Tracking Feed"):
        self.source_name = source_name
        # Per-vessel simulated state, keyed by IMO number. Lives only in process memory - a
        # backend restart resets every vessel's cycle back to step 0 with a freshly randomised
        # origin/waypoint (harmless, just a visible discontinuity in the demo data).
        self._vessel_state: dict[str, dict] = {}

    def _init_state(self, imo: str) -> dict:
        """Create and store fresh cycle state for a vessel we haven't seen before (first poll
        after registration, or after a process restart)."""
        state = {
            "step": 0,
            "origin": random.choice(ORIGIN_PORTS),
            "waypoint": random.choice(WAYPOINT_PORTS),
            "dwell": 0,
        }
        self._vessel_state[imo] = state
        return state

    def poll(self, vessel_imos: list[str], destinations: dict[str, str | None] | None = None) -> list[RawReport]:
        """Advance every given vessel's cycle by one step and return a report for each vessel
        that produced one this tick (a vessel mid-dwell produces none - see below).

        `destinations` maps IMO -> the vessel's configured destination_port (or None), so the
        simulated voyage can actually "arrive" somewhere matching what the vessel is set to -
        this is what lets Section 3.3a's status derivation and Section 3.7's auto-archive be
        exercised realistically instead of against arbitrary random ports.
        """
        destinations = destinations or {}
        now = datetime.now(timezone.utc)
        reports: list[RawReport] = []

        for imo in vessel_imos:
            state = self._vessel_state.get(imo) or self._init_state(imo)
            destination = destinations.get(imo)
            step = state["step"]

            if step == 0:
                # Depart the current origin port, out into open water.
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="departed",
                    event_port=state["origin"],
                    current_location=random.choice(SEA_REGIONS),
                    occurred_at=now,
                    source_name=self.source_name,
                )
            elif step == 1:
                # Arrive somewhere: the vessel's own destination if it has one set (so the
                # status engine can recognise "Arrived at Destination"), otherwise a random
                # waypoint port, simulating an ordinary intermediate port call.
                waypoint = destination or state["waypoint"]
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="arrived",
                    event_port=waypoint,
                    current_location=waypoint,
                    occurred_at=now,
                    source_name=self.source_name,
                )
            elif step == 2 and destination and state["dwell"] < DWELL_TICKS:
                # sitting at the destination - no new report this tick (see module docstring)
                state["dwell"] += 1
                continue
            elif step == 2 and destination:
                # Dwell window elapsed - depart the destination (produces the "Sailed from
                # Destination" status once run through the status engine).
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="departed",
                    event_port=destination,
                    current_location=random.choice(SEA_REGIONS),
                    occurred_at=now,
                    source_name=self.source_name,
                )
            else:
                # cycle back to a new voyage. This tick emits the "departed" report for the
                # new origin (step 0's job), so step must land on 0 - not -1 - or the trailing
                # `state["step"] += 1` below leaves it at 0 anyway and the *next* tick
                # re-executes the step==0 branch (another "departed") instead of advancing to
                # step 1 ("arrived"), producing two consecutive "Sailed X" events per cycle.
                state["step"] = 0
                state["dwell"] = 0
                state["origin"] = random.choice(ORIGIN_PORTS)
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="departed",
                    event_port=state["origin"],
                    current_location=random.choice(SEA_REGIONS),
                    occurred_at=now,
                    source_name=self.source_name,
                )

            # Every branch above that reaches here (i.e. didn't `continue` while dwelling)
            # produced exactly one report - advance to the next step for this vessel's next poll.
            state["step"] += 1
            reports.append(report)

        return reports
