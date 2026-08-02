from datetime import datetime, timezone

from app.db import SessionLocal
from app.models import StatusEvent, TrackingSource, Vessel
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


def test_disabling_mock_source_pauses_tracking_and_reenabling_resumes_it():
    db = SessionLocal()
    try:
        db.add(Vessel(name="MV ABC", imo_number="1234567", destination_port="Pasir Gudang"))
        db.query(TrackingSource).filter(TrackingSource.adapter_key == "mock").update({"enabled": False})
        db.commit()
    finally:
        db.close()

    tracking_worker._adapter._vessel_state.clear()
    assert tracking_worker.run_tracking_poll() == 0

    db = SessionLocal()
    try:
        assert db.query(StatusEvent).count() == 0
        db.query(TrackingSource).filter(TrackingSource.adapter_key == "mock").update({"enabled": True})
        db.commit()
    finally:
        db.close()

    assert tracking_worker.run_tracking_poll() == 1


def test_archived_vessels_are_excluded_from_polling():
    db = SessionLocal()
    try:
        vessel = Vessel(name="MV ABC", imo_number="1234567", destination_port="Pasir Gudang")
        vessel.archived_at = datetime.now(timezone.utc)
        db.add(vessel)
        db.commit()
    finally:
        db.close()

    tracking_worker._adapter._vessel_state.clear()
    assert tracking_worker.run_tracking_poll() == 0


def test_vessel_dwells_at_arrived_destination_across_ticks_instead_of_departing_immediately():
    # Regression test: the mock adapter used to advance every vessel by one step on every
    # tick unconditionally, so a vessel's latest event could never stay ARRIVED_DESTINATION
    # across ticks - the very next poll always moved it straight to "departed". That made
    # the Section 3.7 retention sweep unreachable in live/scheduled operation, since by the
    # time the sweep ran, the vessel had already sailed on. The mock must let an arrived
    # vessel dwell (no new event) for a few ticks before departing again.
    db = SessionLocal()
    try:
        db.add(Vessel(name="MV ABC", imo_number="1234567", destination_port="Pasir Gudang"))
        db.commit()
    finally:
        db.close()

    tracking_worker._adapter._vessel_state.clear()
    tracking_worker.run_tracking_poll()  # step 0: departs origin
    tracking_worker.run_tracking_poll()  # step 1: arrives at destination

    db = SessionLocal()
    try:
        vessel = db.query(Vessel).filter(Vessel.imo_number == "1234567").first()
        assert vessel.events[-1].event_type.value == "arrived_destination"
    finally:
        db.close()

    # One more tick: still dwelling, no new event, latest event still the arrival
    created = tracking_worker.run_tracking_poll()
    assert created == 0

    db = SessionLocal()
    try:
        vessel = db.query(Vessel).filter(Vessel.imo_number == "1234567").first()
        assert len(vessel.events) == 2
        assert vessel.events[-1].event_type.value == "arrived_destination"
    finally:
        db.close()


def test_live_poll_pathway_auto_archives_vessel_past_retention_without_manual_sweep_call(monkeypatch):
    # Regression test for the ordering bug: run_archive_sweep() must run *before* polling
    # within run_tracking_poll(), not after - otherwise the same tick's poll always advances
    # an eligible vessel past ARRIVED_DESTINATION before the sweep ever sees it stuck there.
    monkeypatch.setattr("app.config.settings.arrived_retention_days", 0)

    db = SessionLocal()
    try:
        vessel = Vessel(name="MV ABC", imo_number="1234567", destination_port="Pasir Gudang")
        db.add(vessel)
        db.commit()
    finally:
        db.close()

    tracking_worker._adapter._vessel_state.clear()
    tracking_worker.run_tracking_poll()  # step 0: departs origin
    tracking_worker.run_tracking_poll()  # step 1: arrives at destination - now ARRIVED_DESTINATION

    # With retention_days=0, the very next tick's sweep (which runs before polling) should
    # archive the vessel immediately - proving the live scheduled pathway can reach
    # auto-archive on its own, not just when run_archive_sweep() is called directly.
    tracking_worker.run_tracking_poll()

    db = SessionLocal()
    try:
        vessel = db.query(Vessel).filter(Vessel.imo_number == "1234567").first()
        assert vessel.archived_at is not None
    finally:
        db.close()
