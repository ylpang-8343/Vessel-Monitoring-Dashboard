from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import EventType, ExceptionKind, StatusEvent, Vessel, VesselException
from app.services.exception_detector import detect_for_vessel, run_exception_sweep


def _make_vessel(db, imo="1234567", destination="Pasir Gudang", name="MV Exception"):
    vessel = Vessel(name=name, imo_number=imo, destination_port=destination)
    db.add(vessel)
    db.commit()
    db.refresh(vessel)
    return vessel


def _add_event(db, vessel, event_type, hours_ago=0.0, location="Pasir Gudang", eta=None):
    event = StatusEvent(
        vessel_id=vessel.id,
        event_type=event_type,
        current_location=location,
        last_event_text=f"{event_type.value} {location}",
        source_name="Mock Tracking Feed",
        occurred_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        eta=eta,
    )
    db.add(event)
    db.commit()
    db.refresh(vessel)
    return event


# --- Delay -------------------------------------------------------------------------------


def test_late_arrival_is_flagged_as_delayed():
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        # Departed with an ETA of 8h ago; actually arrived 2h ago -> 6h late.
        _add_event(
            db,
            vessel,
            EventType.ETA_DESTINATION,
            hours_ago=20,
            location="Qingdao",
            eta=datetime.now(timezone.utc) - timedelta(hours=8),
        )
        _add_event(db, vessel, EventType.ARRIVED_DESTINATION, hours_ago=2)

        created = detect_for_vessel(db, vessel)
        kinds = [exc.kind for exc in created]
        assert ExceptionKind.DELAYED in kinds
        delayed = next(exc for exc in created if exc.kind == ExceptionKind.DELAYED)
        assert "after the reported ETA" in delayed.message
    finally:
        db.close()


def test_on_time_arrival_is_not_flagged():
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        # Arrived 2h *before* the reported ETA.
        _add_event(
            db,
            vessel,
            EventType.ETA_DESTINATION,
            hours_ago=20,
            location="Qingdao",
            eta=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        _add_event(db, vessel, EventType.ARRIVED_DESTINATION, hours_ago=0)

        assert [exc.kind for exc in detect_for_vessel(db, vessel)] == []
    finally:
        db.close()


def test_arrival_without_any_reported_eta_is_never_delayed():
    # Nothing to be late against - a vessel whose source never reported an ETA can't be
    # "delayed" in any checkable sense, and guessing would be exactly what Section 3.10 warns off.
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(db, vessel, EventType.ETA_DESTINATION, hours_ago=20, location="Qingdao", eta=None)
        _add_event(db, vessel, EventType.ARRIVED_DESTINATION, hours_ago=0)

        assert [exc.kind for exc in detect_for_vessel(db, vessel)] == []
    finally:
        db.close()


def test_still_underway_past_its_eta_is_flagged_as_delayed():
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(
            db,
            vessel,
            EventType.ETA_DESTINATION,
            hours_ago=30,
            location="Qingdao",
            eta=datetime.now(timezone.utc) - timedelta(hours=5),
        )
        created = detect_for_vessel(db, vessel)
        assert [exc.kind for exc in created] == [ExceptionKind.DELAYED]
        assert "Still en route" in created[0].message
    finally:
        db.close()


def test_latest_eta_supersedes_an_earlier_one():
    # A source that revises its ETA is giving better information; holding the vessel to the
    # superseded estimate would flag a delay the source itself no longer claims.
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(
            db,
            vessel,
            EventType.ETA_DESTINATION,
            hours_ago=30,
            location="Qingdao",
            eta=datetime.now(timezone.utc) - timedelta(hours=20),  # old, badly missed ETA
        )
        _add_event(
            db,
            vessel,
            EventType.ETA_DESTINATION,
            hours_ago=10,
            location="South China Sea",
            eta=datetime.now(timezone.utc) + timedelta(hours=6),  # revised: still in the future
        )
        assert [exc.kind for exc in detect_for_vessel(db, vessel)] == []
    finally:
        db.close()


# --- Long port stay ----------------------------------------------------------------------


def test_long_port_stay_is_flagged_past_the_threshold(monkeypatch):
    monkeypatch.setattr("app.config.settings.long_port_stay_hours", 24)
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=40, location="Singapore Anchorage")

        created = detect_for_vessel(db, vessel)
        assert ExceptionKind.LONG_PORT_STAY in [exc.kind for exc in created]
    finally:
        db.close()


def test_short_port_stay_is_not_flagged(monkeypatch):
    monkeypatch.setattr("app.config.settings.long_port_stay_hours", 24)
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=2, location="Singapore Anchorage")

        assert ExceptionKind.LONG_PORT_STAY not in [exc.kind for exc in detect_for_vessel(db, vessel)]
    finally:
        db.close()


# --- Unexpected port call ----------------------------------------------------------------


def test_unexpected_port_call_is_flagged():
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=50, location="Singapore Anchorage")
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=1, location="Xiamen")  # never seen before

        created = detect_for_vessel(db, vessel)
        assert ExceptionKind.UNEXPECTED_PORT_CALL in [exc.kind for exc in created]
    finally:
        db.close()


def test_previously_visited_port_is_not_unexpected():
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=50, location="Singapore Anchorage")
        _add_event(db, vessel, EventType.ETA_DESTINATION, hours_ago=25, location="South China Sea")
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=1, location="Singapore Anchorage")

        assert ExceptionKind.UNEXPECTED_PORT_CALL not in [exc.kind for exc in detect_for_vessel(db, vessel)]
    finally:
        db.close()


def test_arriving_at_the_configured_destination_is_never_unexpected():
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=50, location="Singapore Anchorage")
        # AT_PORT at the destination itself - the status engine would normally call this
        # ARRIVED_DESTINATION, but guard the detector against it regardless.
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=1, location="Pasir Gudang")

        assert ExceptionKind.UNEXPECTED_PORT_CALL not in [exc.kind for exc in detect_for_vessel(db, vessel)]
    finally:
        db.close()


def test_a_vessels_first_ever_port_call_is_not_unexpected():
    # With one data point there is no pattern to deviate from.
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(db, vessel, EventType.AT_PORT, hours_ago=1, location="Xiamen")

        assert ExceptionKind.UNEXPECTED_PORT_CALL not in [exc.kind for exc in detect_for_vessel(db, vessel)]
    finally:
        db.close()


# --- Dedupe and sweep --------------------------------------------------------------------


def test_the_same_exception_is_only_recorded_once():
    # This is what stops an ongoing condition re-alerting on every poll tick.
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(
            db,
            vessel,
            EventType.ETA_DESTINATION,
            hours_ago=30,
            location="Qingdao",
            eta=datetime.now(timezone.utc) - timedelta(hours=5),
        )

        first = detect_for_vessel(db, vessel)
        second = detect_for_vessel(db, vessel)
        third = detect_for_vessel(db, vessel)

        assert len(first) == 1
        assert second == [] and third == []
        assert db.query(VesselException).count() == 1
    finally:
        db.close()


def test_sweep_skips_archived_vessels():
    db = SessionLocal()
    try:
        vessel = _make_vessel(db)
        _add_event(
            db,
            vessel,
            EventType.ETA_DESTINATION,
            hours_ago=30,
            location="Qingdao",
            eta=datetime.now(timezone.utc) - timedelta(hours=5),
        )
        vessel.archived_at = datetime.now(timezone.utc)
        db.commit()

        assert run_exception_sweep(db) == []
    finally:
        db.close()


def test_sweep_covers_every_active_vessel():
    db = SessionLocal()
    try:
        for imo in ("1111111", "2222222"):
            vessel = _make_vessel(db, imo=imo, name=f"MV {imo}")
            _add_event(
                db,
                vessel,
                EventType.ETA_DESTINATION,
                hours_ago=30,
                location="Qingdao",
                eta=datetime.now(timezone.utc) - timedelta(hours=5),
            )

        created = run_exception_sweep(db)
        assert len(created) == 2
        assert {exc.kind for exc in created} == {ExceptionKind.DELAYED}
    finally:
        db.close()
