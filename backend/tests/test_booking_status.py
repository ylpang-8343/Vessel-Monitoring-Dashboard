from datetime import datetime, timezone

from app.models import BookingStatus
from app.services.booking_status import format_last_event_text
from app.sources.booking_base import RawBookingReport


def _report(status: BookingStatus) -> RawBookingReport:
    return RawBookingReport(
        booking_number="TCLU7788990",
        status=status,
        current_location="wherever",
        occurred_at=datetime(2026, 7, 24, 9, 40, tzinfo=timezone.utc),
        source_name="Mock Booking Feed",
    )


def test_pol_side_stages_name_the_loading_port():
    pol, pod = "Shanghai", "Port Klang West"
    assert format_last_event_text(_report(BookingStatus.BOOKING_CONFIRMED), pol, pod) == (
        "Booking Confirmed Shanghai — 24 Jul 2026, 09:40"
    )
    assert format_last_event_text(_report(BookingStatus.LOADED), pol, pod) == "Loaded Shanghai — 24 Jul 2026, 09:40"
    assert format_last_event_text(_report(BookingStatus.IN_TRANSIT), pol, pod) == (
        "Departed Shanghai — 24 Jul 2026, 09:40"
    )


def test_pod_side_stages_name_the_discharge_port():
    pol, pod = "Shanghai", "Port Klang West"
    assert format_last_event_text(_report(BookingStatus.DISCHARGED), pol, pod) == (
        "Discharged Port Klang West — 24 Jul 2026, 09:40"
    )
    assert format_last_event_text(_report(BookingStatus.GATE_OUT), pol, pod) == (
        "Gate Out Port Klang West — 24 Jul 2026, 09:40"
    )
