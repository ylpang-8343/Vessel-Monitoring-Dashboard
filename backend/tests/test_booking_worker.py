from app.db import SessionLocal
from app.models import Booking, BookingEvent, TrackingSource
from app.services import booking_worker


def test_run_booking_poll_creates_events_for_every_active_booking():
    db = SessionLocal()
    try:
        db.add(Booking(booking_number="AAAA0000001", shipping_line="ONE", port_of_loading="Xiamen", port_of_discharge="Pasir Gudang"))
        db.add(Booking(booking_number="BBBB0000002", shipping_line="MSC", port_of_loading="Ningbo", port_of_discharge="Butterworth"))
        db.commit()
    finally:
        db.close()

    booking_worker._adapter._booking_step.clear()
    created = booking_worker.run_booking_poll()
    assert created == 2

    db = SessionLocal()
    try:
        events = db.query(BookingEvent).all()
        assert len(events) == 2
        for event in events:
            assert event.current_location
            assert event.last_event_text
            assert event.source_name == "Mock Booking Feed"
    finally:
        db.close()


def test_run_booking_poll_advances_through_lifecycle_stages():
    db = SessionLocal()
    try:
        db.add(Booking(booking_number="TCLU7788990", shipping_line="Maersk", port_of_loading="Shanghai", port_of_discharge="Port Klang West"))
        db.commit()
    finally:
        db.close()

    booking_worker._adapter._booking_step.clear()
    booking_worker.run_booking_poll()  # booking_confirmed
    booking_worker.run_booking_poll()  # loaded

    db = SessionLocal()
    try:
        events = db.query(BookingEvent).order_by(BookingEvent.id).all()
        assert [e.status.value for e in events] == ["booking_confirmed", "loaded"]
    finally:
        db.close()


def test_run_booking_poll_is_noop_with_no_bookings():
    booking_worker._adapter._booking_step.clear()
    assert booking_worker.run_booking_poll() == 0


def test_disabling_mock_booking_source_pauses_polling_and_reenabling_resumes_it():
    db = SessionLocal()
    try:
        db.add(Booking(booking_number="AAAA0000001", shipping_line="ONE", port_of_loading="Xiamen", port_of_discharge="Pasir Gudang"))
        db.query(TrackingSource).filter(TrackingSource.adapter_key == "mock_booking").update({"enabled": False})
        db.commit()
    finally:
        db.close()

    booking_worker._adapter._booking_step.clear()
    assert booking_worker.run_booking_poll() == 0

    db = SessionLocal()
    try:
        assert db.query(BookingEvent).count() == 0
        db.query(TrackingSource).filter(TrackingSource.adapter_key == "mock_booking").update({"enabled": True})
        db.commit()
    finally:
        db.close()

    assert booking_worker.run_booking_poll() == 1


def test_archived_bookings_are_excluded_from_polling():
    from datetime import datetime, timezone

    db = SessionLocal()
    try:
        booking = Booking(booking_number="AAAA0000001", shipping_line="ONE", port_of_loading="Xiamen", port_of_discharge="Pasir Gudang")
        booking.archived_at = datetime.now(timezone.utc)
        db.add(booking)
        db.commit()
    finally:
        db.close()

    booking_worker._adapter._booking_step.clear()
    assert booking_worker.run_booking_poll() == 0


def test_booking_lifecycle_stops_producing_events_after_gate_out():
    db = SessionLocal()
    try:
        db.add(Booking(booking_number="TCLU7788990", shipping_line="Maersk", port_of_loading="Shanghai", port_of_discharge="Port Klang West"))
        db.commit()
    finally:
        db.close()

    booking_worker._adapter._booking_step.clear()
    for _ in range(5):
        booking_worker.run_booking_poll()  # walks all five stages to GATE_OUT

    # One more tick past GATE_OUT: no new event, matching the mock adapter's terminal lifecycle.
    assert booking_worker.run_booking_poll() == 0

    db = SessionLocal()
    try:
        events = db.query(BookingEvent).order_by(BookingEvent.id).all()
        assert len(events) == 5
        assert events[-1].status.value == "gate_out"
    finally:
        db.close()
