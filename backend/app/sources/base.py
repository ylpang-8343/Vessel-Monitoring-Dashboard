from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass
class RawReport:
    """A single position/port-call report for one vessel, as a tracking source would emit it.

    event_kind "arrived"/"departed" carries `event_port` (the port involved).
    `current_location` is the vessel's present position as the source describes it
    (a port name for "arrived", a sea/region name for "departed") and is what the
    dashboard's Current Location column shows.
    """

    vessel_imo: str
    event_kind: Literal["arrived", "departed"]
    event_port: str
    current_location: str
    occurred_at: datetime
    source_name: str


class TrackingSourceAdapter(ABC):
    """Interface for a vessel-tracking data source.

    Swap in a real scraper/API client later by implementing this interface —
    the status engine and dashboard never need to change.
    """

    # Matches TrackingSource.adapter_key in models.py - identifies which adapter implementation
    # a given TrackingSource row should be polled with.
    adapter_key: str

    @abstractmethod
    def poll(self, vessel_imos: list[str]) -> list[RawReport]:
        """Return any new reports available for the given vessels since the last poll."""
        raise NotImplementedError
