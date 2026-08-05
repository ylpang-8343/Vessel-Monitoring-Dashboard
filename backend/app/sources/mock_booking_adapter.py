"""Simulated container/booking source (Section 4), the companion to sources/mock_adapter.py.

Advances each booking through its lifecycle by one stage every poll tick, same as the vessel
mock adapter - exercising the full ingest -> BookingEvent -> Container/Booking table pipeline
end-to-end without depending on real carrier-portal access (ONE, Maersk, MSC, CMA CGM, InterAsia
- Section 8.1), which the proposal notes would need credentials not yet available (Section 10).

Unlike the vessel mock adapter, this cycle is deliberately *linear, not repeating*: a real
booking/container has a one-way journey from Booking Confirmed through to Gate Out and then it's
simply done - there's no realistic "next voyage" for the same booking number the way a vessel
sails again after arriving. So once a booking reaches GATE_OUT, poll() stops emitting reports for
it entirely rather than looping back to BOOKING_CONFIRMED.

Swap this out for a real carrier-API/scraper-backed adapter later via the same
BookingSourceAdapter interface - nothing else in the app needs to change.
"""

from datetime import datetime, timezone

from app.models import BookingStatus
from app.sources.booking_base import BookingSourceAdapter, RawBookingReport

# Ordered lifecycle - index is this booking's "step". Every booking walks this list once, in
# order, one stage per poll tick.
_STAGES: list[BookingStatus] = [
    BookingStatus.BOOKING_CONFIRMED,
    BookingStatus.LOADED,
    BookingStatus.IN_TRANSIT,
    BookingStatus.DISCHARGED,
    BookingStatus.GATE_OUT,
]


class MockBookingAdapter(BookingSourceAdapter):
    """Stand-in BookingSourceAdapter that advances a fixed, one-way lifecycle per booking
    instead of calling a real carrier tracking portal. See the module docstring for why this
    cycle is linear rather than repeating like the vessel mock adapter's."""

    adapter_key = "mock_booking"

    def __init__(self, source_name: str = "Mock Booking Feed"):
        self.source_name = source_name
        # Per-booking simulated step, keyed by booking_number. In-memory only, like
        # MockAdapter._vessel_state - resets to step 0 on a backend restart (harmless, just a
        # visible discontinuity in demo data).
        self._booking_step: dict[str, int] = {}

    def poll(
        self,
        booking_numbers: list[str],
        ports: dict[str, tuple[str, str]] | None = None,
    ) -> list[RawBookingReport]:
        """Advance every given booking's lifecycle by one stage and return a report for each
        booking that produced one this tick. A booking already at GATE_OUT produces nothing -
        its lifecycle is over (see module docstring).

        `ports` maps booking_number -> (port_of_loading, port_of_discharge), so the simulated
        current_location can actually reference the booking's own real ports instead of
        arbitrary placeholder text - the same role `destinations` plays in MockAdapter.poll().
        """
        ports = ports or {}
        now = datetime.now(timezone.utc)
        reports: list[RawBookingReport] = []

        for number in booking_numbers:
            step = self._booking_step.get(number, 0)
            if step >= len(_STAGES):
                # Already reached GATE_OUT on a previous tick - nothing more to report, ever.
                continue

            pol, pod = ports.get(number, ("Port of Loading", "Port of Discharge"))
            status = _STAGES[step]
            current_location = {
                BookingStatus.BOOKING_CONFIRMED: pol,
                BookingStatus.LOADED: pol,
                BookingStatus.IN_TRANSIT: f"At sea, en route to {pod}",
                BookingStatus.DISCHARGED: pod,
                BookingStatus.GATE_OUT: pod,
            }[status]

            report = RawBookingReport(
                booking_number=number,
                status=status,
                current_location=current_location,
                occurred_at=now,
                source_name=self.source_name,
            )
            reports.append(report)
            self._booking_step[number] = step + 1

        return reports
