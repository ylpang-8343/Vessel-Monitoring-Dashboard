"""Simulated tracking source.

Advances each vessel through a simple, repeating voyage cycle by one step every time
poll() is called (i.e. once per tracking-worker tick). This exercises the full
ingest -> status engine -> StatusEvent -> dashboard pipeline end-to-end without
depending on real MarineTraffic/VesselFinder/Polestar GMDA access, which the
proposal notes requires credentials/API terms not yet available (Section 10).

Swap this out for a real scraper/API-backed adapter later via the same
TrackingSourceAdapter interface -- nothing else in the app needs to change.
"""

import random
from datetime import datetime, timezone

from app.sources.base import RawReport, TrackingSourceAdapter

ORIGIN_PORTS = ["Qingdao", "Shanghai", "Xiamen", "Ningbo"]
SEA_REGIONS = ["South China Sea", "Strait of Malacca", "Singapore Strait", "Andaman Sea"]
WAYPOINT_PORTS = ["Singapore Anchorage", "Port Klang South"]


class MockAdapter(TrackingSourceAdapter):
    adapter_key = "mock"

    def __init__(self, source_name: str = "Mock Tracking Feed"):
        self.source_name = source_name
        self._vessel_state: dict[str, dict] = {}

    def _init_state(self, imo: str) -> dict:
        state = {
            "step": 0,
            "origin": random.choice(ORIGIN_PORTS),
            "waypoint": random.choice(WAYPOINT_PORTS),
        }
        self._vessel_state[imo] = state
        return state

    def poll(self, vessel_imos: list[str], destinations: dict[str, str | None] | None = None) -> list[RawReport]:
        destinations = destinations or {}
        now = datetime.now(timezone.utc)
        reports: list[RawReport] = []

        for imo in vessel_imos:
            state = self._vessel_state.get(imo) or self._init_state(imo)
            destination = destinations.get(imo)
            step = state["step"]

            if step == 0:
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="departed",
                    event_port=state["origin"],
                    current_location=random.choice(SEA_REGIONS),
                    occurred_at=now,
                    source_name=self.source_name,
                )
            elif step == 1:
                waypoint = destination or state["waypoint"]
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="arrived",
                    event_port=waypoint,
                    current_location=waypoint,
                    occurred_at=now,
                    source_name=self.source_name,
                )
            elif step == 2 and destination:
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="departed",
                    event_port=destination,
                    current_location=random.choice(SEA_REGIONS),
                    occurred_at=now,
                    source_name=self.source_name,
                )
            else:
                # cycle back to a new voyage
                state["step"] = -1
                state["origin"] = random.choice(ORIGIN_PORTS)
                report = RawReport(
                    vessel_imo=imo,
                    event_kind="departed",
                    event_port=state["origin"],
                    current_location=random.choice(SEA_REGIONS),
                    occurred_at=now,
                    source_name=self.source_name,
                )

            state["step"] += 1
            reports.append(report)

        return reports
