from app.models import BookingStatus
from app.sources.mock_booking_adapter import MockBookingAdapter


def _poll_once(adapter, number, ports):
    reports = adapter.poll([number], ports)
    return reports[0] if reports else None


def test_lifecycle_advances_through_all_five_stages_in_order():
    adapter = MockBookingAdapter()
    number = "TCLU7788990"
    ports = {number: ("Shanghai", "Port Klang West")}

    stages = [_poll_once(adapter, number, ports).status for _ in range(5)]

    assert stages == [
        BookingStatus.BOOKING_CONFIRMED,
        BookingStatus.LOADED,
        BookingStatus.IN_TRANSIT,
        BookingStatus.DISCHARGED,
        BookingStatus.GATE_OUT,
    ]


def test_lifecycle_is_linear_not_repeating_after_gate_out():
    # Regression guard for the module's core design decision (see its docstring): unlike the
    # vessel mock adapter's repeating voyage cycle, a booking's lifecycle must stay terminal once
    # it reaches GATE_OUT - it should never loop back to BOOKING_CONFIRMED.
    adapter = MockBookingAdapter()
    number = "TCLU7788990"
    ports = {number: ("Shanghai", "Port Klang West")}

    for _ in range(5):
        _poll_once(adapter, number, ports)

    assert _poll_once(adapter, number, ports) is None
    assert _poll_once(adapter, number, ports) is None  # stays terminal on further polls too


def test_current_location_reflects_pol_pod_and_at_sea_description():
    adapter = MockBookingAdapter()
    number = "MSKU4455667"
    ports = {number: ("Ningbo", "Butterworth")}

    booking_confirmed = _poll_once(adapter, number, ports)
    loaded = _poll_once(adapter, number, ports)
    in_transit = _poll_once(adapter, number, ports)
    discharged = _poll_once(adapter, number, ports)
    gate_out = _poll_once(adapter, number, ports)

    assert booking_confirmed.current_location == "Ningbo"
    assert loaded.current_location == "Ningbo"
    assert in_transit.current_location == "At sea, en route to Butterworth"
    assert discharged.current_location == "Butterworth"
    assert gate_out.current_location == "Butterworth"


def test_multiple_bookings_progress_independently():
    adapter = MockBookingAdapter()
    ports = {
        "AAAA0000001": ("Qingdao", "Pasir Gudang"),
        "BBBB0000002": ("Xiamen", "Butterworth"),
    }

    # Advance only the first booking twice, the second once.
    adapter.poll(["AAAA0000001"], ports)
    adapter.poll(["AAAA0000001"], ports)
    adapter.poll(["BBBB0000002"], ports)

    reports = adapter.poll(["AAAA0000001", "BBBB0000002"], ports)
    by_number = {r.booking_number: r for r in reports}
    assert by_number["AAAA0000001"].status == BookingStatus.IN_TRANSIT  # 3rd stage
    assert by_number["BBBB0000002"].status == BookingStatus.LOADED  # 2nd stage
