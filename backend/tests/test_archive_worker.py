from datetime import datetime, timedelta, timezone

from app.models import EventType, StatusEvent, Vessel
from app.services.archive_worker import run_archive_sweep


def _vessel_with_event(db_session, imo, event_type, occurred_at, destination="Pasir Gudang"):
    vessel = Vessel(name=f"MV {imo}", imo_number=imo, destination_port=destination)
    db_session.add(vessel)
    db_session.commit()
    db_session.refresh(vessel)

    db_session.add(
        StatusEvent(
            vessel_id=vessel.id,
            event_type=event_type,
            current_location=destination,
            last_event_text=f"Arrived {destination}",
            source_name="Mock Tracking Feed",
            occurred_at=occurred_at,
        )
    )
    db_session.commit()
    return vessel


def test_archives_vessel_past_retention_window(db_session):
    old_arrival = datetime.now(timezone.utc) - timedelta(days=11)
    vessel = _vessel_with_event(db_session, "1234567", EventType.ARRIVED_DESTINATION, old_arrival)

    archived_count = run_archive_sweep(db_session, retention_days=10)

    assert archived_count == 1
    db_session.refresh(vessel)
    assert vessel.archived_at is not None


def test_leaves_recent_arrival_alone(db_session):
    recent_arrival = datetime.now(timezone.utc) - timedelta(days=2)
    vessel = _vessel_with_event(db_session, "1234567", EventType.ARRIVED_DESTINATION, recent_arrival)

    archived_count = run_archive_sweep(db_session, retention_days=10)

    assert archived_count == 0
    db_session.refresh(vessel)
    assert vessel.archived_at is None


def test_ignores_vessels_not_currently_arrived(db_session):
    old_event = datetime.now(timezone.utc) - timedelta(days=20)
    vessel = _vessel_with_event(db_session, "1234567", EventType.SAILED_FROM_DESTINATION, old_event)

    archived_count = run_archive_sweep(db_session, retention_days=10)

    assert archived_count == 0
    db_session.refresh(vessel)
    assert vessel.archived_at is None


def test_ignores_vessel_with_no_events(db_session):
    vessel = Vessel(name="MV Empty", imo_number="7788990", destination_port="Pasir Gudang")
    db_session.add(vessel)
    db_session.commit()

    archived_count = run_archive_sweep(db_session, retention_days=10)

    assert archived_count == 0


def test_does_not_recount_already_archived_vessel(db_session):
    old_arrival = datetime.now(timezone.utc) - timedelta(days=11)
    vessel = _vessel_with_event(db_session, "1234567", EventType.ARRIVED_DESTINATION, old_arrival)
    run_archive_sweep(db_session, retention_days=10)

    archived_count = run_archive_sweep(db_session, retention_days=10)

    assert archived_count == 0
