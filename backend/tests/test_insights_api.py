from datetime import datetime, timedelta, timezone


def _seed_delayed_vessel(db_session, imo="1234567", name="MV Late"):
    """A vessel that is underway and already past its reported ETA, so the detector will flag it."""
    from app.models import EventType, StatusEvent, Vessel

    vessel = Vessel(name=name, imo_number=imo, destination_port="Pasir Gudang")
    db_session.add(vessel)
    db_session.commit()
    db_session.refresh(vessel)

    db_session.add(
        StatusEvent(
            vessel_id=vessel.id,
            event_type=EventType.ETA_DESTINATION,
            current_location="Qingdao",
            last_event_text="Sailed Qingdao",
            source_name="Mock Tracking Feed",
            occurred_at=datetime.now(timezone.utc) - timedelta(hours=30),
            eta=datetime.now(timezone.utc) - timedelta(hours=5),
        )
    )
    db_session.commit()
    db_session.refresh(vessel)
    return vessel


def test_ai_status_reports_unconfigured_by_default(client):
    resp = client.get("/api/insights/ai-status")
    assert resp.status_code == 200
    assert resp.json() == {"configured": False}


def test_ai_status_reports_configured_once_a_key_is_set(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")
    assert client.get("/api/insights/ai-status").json() == {"configured": True}


def test_exceptions_list_is_empty_before_detection_runs(client):
    assert client.get("/api/insights/exceptions").json() == []


def test_exceptions_list_returns_detected_exceptions(client, db_session):
    from app.services.exception_detector import run_exception_sweep

    _seed_delayed_vessel(db_session)
    run_exception_sweep(db_session)

    body = client.get("/api/insights/exceptions").json()
    assert len(body) == 1
    assert body[0]["kind"] == "delayed"
    assert body[0]["vessel_imo"] == "1234567"
    assert body[0]["vessel_name"] == "MV Late"
    assert "Still en route" in body[0]["message"]


def test_exceptions_list_filters_by_kind(client, db_session):
    from app.services.exception_detector import run_exception_sweep

    _seed_delayed_vessel(db_session)
    run_exception_sweep(db_session)

    assert len(client.get("/api/insights/exceptions", params={"kind": "delayed"}).json()) == 1
    assert client.get("/api/insights/exceptions", params={"kind": "long_port_stay"}).json() == []


def test_summary_is_null_before_one_is_generated(client, db_session):
    _seed_delayed_vessel(db_session)
    resp = client.get("/api/insights/vessels/1234567/summary")
    assert resp.status_code == 200
    assert resp.json() is None


def test_summary_generation_is_503_without_an_api_key(client, db_session):
    # Unavailable rather than broken, same as PDF bulk upload without a key.
    _seed_delayed_vessel(db_session)
    resp = client.post("/api/insights/vessels/1234567/summary")
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_summary_is_generated_cached_and_marked_stale_when_events_move_on(client, db_session, monkeypatch):
    from app.models import EventType, StatusEvent

    _seed_delayed_vessel(db_session)
    monkeypatch.setattr(
        "app.services.ai_service.generate_voyage_summary",
        lambda vessel, events: "MV Late sailed from Qingdao and is en route to Pasir Gudang.",
    )

    created = client.post("/api/insights/vessels/1234567/summary")
    assert created.status_code == 200
    body = created.json()
    assert body["summary"].startswith("MV Late sailed")
    assert body["source_event_count"] == 1
    assert body["is_stale"] is False

    # A subsequent GET serves the cache without regenerating (no API call needed).
    assert client.get("/api/insights/vessels/1234567/summary").json()["summary"] == body["summary"]

    # A new tracking event lands -> the cached summary is now behind the timeline and says so.
    vessel_id = db_session.query(StatusEvent).first().vessel_id
    db_session.add(
        StatusEvent(
            vessel_id=vessel_id,
            event_type=EventType.ARRIVED_DESTINATION,
            current_location="Pasir Gudang",
            last_event_text="Arrived Pasir Gudang",
            source_name="Mock Tracking Feed",
            occurred_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()

    assert client.get("/api/insights/vessels/1234567/summary").json()["is_stale"] is True


def test_regenerating_overwrites_rather_than_accumulating(client, db_session, monkeypatch):
    from app.models import VoyageSummary

    _seed_delayed_vessel(db_session)
    monkeypatch.setattr("app.services.ai_service.generate_voyage_summary", lambda vessel, events: "First.")
    client.post("/api/insights/vessels/1234567/summary")
    monkeypatch.setattr("app.services.ai_service.generate_voyage_summary", lambda vessel, events: "Second.")
    resp = client.post("/api/insights/vessels/1234567/summary")

    assert resp.json()["summary"] == "Second."
    assert db_session.query(VoyageSummary).count() == 1


def test_summary_404s_for_an_unknown_vessel(client):
    assert client.get("/api/insights/vessels/0000000/summary").status_code == 404
    assert client.post("/api/insights/vessels/0000000/summary").status_code == 404


def test_history_caps_the_exception_panel_but_reports_the_true_total(client, db_session):
    """Regression test: a vessel that is repeatedly late records one exception per voyage, and
    the history page originally rendered every one of them - 19 stacked alerts pushed the
    movement timeline (the point of the page) off the screen. The panel now shows a bounded
    slice while still reporting the real count."""
    from app.models import ExceptionKind, VesselException
    from app.routers.history import MAX_HISTORY_EXCEPTIONS

    vessel = _seed_delayed_vessel(db_session)
    for index in range(MAX_HISTORY_EXCEPTIONS + 7):
        db_session.add(
            VesselException(
                vessel_id=vessel.id,
                kind=ExceptionKind.DELAYED,
                message=f"Late arrival #{index}",
                dedupe_key=f"{vessel.id}:delayed:test:{index}",
            )
        )
    db_session.commit()

    body = client.get("/api/vessels/1234567/history").json()
    assert len(body["exceptions"]) == MAX_HISTORY_EXCEPTIONS
    assert body["exception_count"] == MAX_HISTORY_EXCEPTIONS + 7


def test_exceptions_list_respects_its_limit(client, db_session):
    from app.models import ExceptionKind, VesselException

    vessel = _seed_delayed_vessel(db_session)
    for index in range(10):
        db_session.add(
            VesselException(
                vessel_id=vessel.id,
                kind=ExceptionKind.DELAYED,
                message=f"Late arrival #{index}",
                dedupe_key=f"{vessel.id}:delayed:test:{index}",
            )
        )
    db_session.commit()

    assert len(client.get("/api/insights/exceptions", params={"limit": 4}).json()) == 4
    assert len(client.get("/api/insights/exceptions").json()) == 10


def test_insights_require_login():
    from fastapi.testclient import TestClient

    from app.main import app

    anon = TestClient(app)
    assert anon.get("/api/insights/exceptions").status_code == 401
    assert anon.get("/api/insights/ai-status").status_code == 401


def test_history_includes_predicted_eta_and_exceptions(client, db_session):
    from app.models import EventType, StatusEvent
    from app.services.exception_detector import run_exception_sweep

    vessel = _seed_delayed_vessel(db_session)
    # Give it one completed prior voyage so a prediction has a basis.
    base = datetime.now(timezone.utc) - timedelta(hours=200)
    db_session.add_all(
        [
            StatusEvent(
                vessel_id=vessel.id,
                event_type=EventType.ETA_DESTINATION,
                current_location="Qingdao",
                last_event_text="Sailed Qingdao",
                source_name="Mock Tracking Feed",
                occurred_at=base,
            ),
            StatusEvent(
                vessel_id=vessel.id,
                event_type=EventType.ARRIVED_DESTINATION,
                current_location="Pasir Gudang",
                last_event_text="Arrived Pasir Gudang",
                source_name="Mock Tracking Feed",
                occurred_at=base + timedelta(hours=40),
            ),
        ]
    )
    db_session.commit()
    run_exception_sweep(db_session)

    body = client.get("/api/vessels/1234567/history").json()
    assert body["predicted_eta"] is not None
    assert body["predicted_eta"]["sample_size"] == 1
    assert body["predicted_eta"]["typical_duration_hours"] == 40.0
    assert [exc["kind"] for exc in body["exceptions"]] == ["delayed"]
    # The ETA the source reported is exposed on the timeline (Section 3.3's captured field).
    assert any(event["eta"] is not None for event in body["timeline"])
