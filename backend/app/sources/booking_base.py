"""Pluggable data-source interface for the Container/Booking Tracking module (Section 4) -
the same "swap a real adapter in later without touching anything downstream" pattern as
sources/base.py's TrackingSourceAdapter, applied to carrier booking records instead of vessel
position reports (see that module's docstring for the shared rationale)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.models import BookingStatus


@dataclass
class RawBookingReport:
    """A single booking-status update, as a carrier's tracking portal (ONE, Maersk, MSC, CMA CGM,
    InterAsia - Section 8.1) would report it.

    Unlike vessel tracking's RawReport, `status` is taken directly from the source rather than
    derived/inferred (see models.BookingStatus's docstring) - carrier booking records already
    state which of the five lifecycle stages applies, which is exactly what makes this data more
    reliable than AIS position data for load/discharge visibility (Section 3.10).
    """

    booking_number: str
    status: BookingStatus
    # Where the cargo is right now, per this report - shown directly in the Current Location
    # column (Section 4).
    current_location: str
    occurred_at: datetime
    source_name: str


class BookingSourceAdapter(ABC):
    """Interface for a container/booking tracking data source.

    Swap in a real carrier-portal scraper/API client later by implementing this interface -
    nothing in the router or presentation layer needs to change.
    """

    # Matches TrackingSource.adapter_key - identifies which adapter implementation a given
    # TrackingSource row (with kind=CONTAINER) should be polled with.
    adapter_key: str

    @abstractmethod
    def poll(self, booking_numbers: list[str]) -> list[RawBookingReport]:
        """Return any new reports available for the given bookings since the last poll."""
        raise NotImplementedError
