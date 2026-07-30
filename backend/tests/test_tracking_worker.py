from app.db import SessionLocal
from app.models import StatusEvent, Vessel
from app.services import tracking_worker


def test_run_tracking_poll_creates_events_for_every_vessel():
    db = SessionLocal()
    try:
        db.add(Vessel(name="MV ABC", imo_number="1234567", destination_port="Pasir Gudang"))
        db.add(Vessel(name="MV Horizon Star", imo_number="9876543"))
        db.commit()
    finally:
        db.close()

    tracking_worker._adapter._vessel_state.clear()
    created = tracking_worker.run_tracking_poll()
    assert created == 2

    db = SessionLocal()
    try:
        events = db.query(StatusEvent).all()
        assert len(events) == 2
        for event in events:
            assert event.current_location
            assert event.last_event_text
            assert event.source_name == "Mock Tracking Feed"
    finally:
        db.close()


def test_run_tracking_poll_advances_vessel_through_voyage_steps():
    db = SessionLocal()
    try:
        db.add(Vessel(name="MV Ocean Pearl", imo_number="2233445", destination_port="Pasir Gudang"))
        db.commit()
    finally:
        db.close()

    tracking_worker._adapter._vessel_state.clear()
    tracking_worker.run_tracking_poll()  # step 0: departs origin
    tracking_worker.run_tracking_poll()  # step 1: arrives at destination

    db = SessionLocal()
    try:
        events = db.query(StatusEvent).order_by(StatusEvent.id).all()
        assert len(events) == 2
        assert events[-1].event_type.value == "arrived_destination"
    finally:
        db.close()


def test_run_tracking_poll_is_noop_with_no_vessels():
    tracking_worker._adapter._vessel_state.clear()
    assert tracking_worker.run_tracking_poll() == 0
