def _create(client, **overrides):
    payload = {
        "booking_number": "tclu7788990",
        "shipping_line": "Maersk",
        "port_of_loading": "Shanghai",
        "port_of_discharge": "Port Klang West",
        **overrides,
    }
    return client.post("/api/bookings", json=payload)


def test_create_booking_normalizes_number_to_uppercase(client):
    resp = _create(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["booking_number"] == "TCLU7788990"
    assert body["current_location"] is None
    assert body["last_event_status"] is None


def test_rejects_duplicate_booking_number_case_insensitively(client):
    _create(client, booking_number="ONEYBOOKG12345")
    resp = _create(client, booking_number="oneybookg12345", shipping_line="ONE")
    assert resp.status_code == 409


def test_rejects_missing_required_field(client):
    resp = client.post(
        "/api/bookings",
        json={"booking_number": "ABCD0000001", "shipping_line": "MSC", "port_of_loading": "Ningbo"},
    )
    assert resp.status_code == 422


def test_list_bookings_search_by_number_line_or_port(client):
    _create(client, booking_number="AAAA0000001", shipping_line="ONE", port_of_loading="Xiamen", port_of_discharge="Butterworth")
    _create(client, booking_number="BBBB0000002", shipping_line="CMA CGM", port_of_loading="Ningbo", port_of_discharge="Pasir Gudang")

    assert len(client.get("/api/bookings", params={"q": "ONE"}).json()) == 1
    assert len(client.get("/api/bookings", params={"q": "AAAA0000001"}).json()) == 1
    assert len(client.get("/api/bookings", params={"q": "Butterworth"}).json()) == 1
    assert len(client.get("/api/bookings", params={"q": "Ningbo"}).json()) == 1
    assert len(client.get("/api/bookings").json()) == 2


def test_list_bookings_filters_by_status(client, db_session):
    from datetime import datetime, timezone

    from app.models import Booking, BookingEvent, BookingStatus

    loaded = Booking(booking_number="AAAA0000001", shipping_line="ONE", port_of_loading="Xiamen", port_of_discharge="Butterworth")
    confirmed = Booking(booking_number="BBBB0000002", shipping_line="MSC", port_of_loading="Ningbo", port_of_discharge="Pasir Gudang")
    db_session.add_all([loaded, confirmed])
    db_session.commit()
    db_session.refresh(loaded)
    db_session.refresh(confirmed)

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            BookingEvent(
                booking_id=loaded.id,
                status=BookingStatus.LOADED,
                current_location="Xiamen",
                last_event_text="Loaded Xiamen — now",
                source_name="Mock Booking Feed",
                occurred_at=now,
            ),
            BookingEvent(
                booking_id=confirmed.id,
                status=BookingStatus.BOOKING_CONFIRMED,
                current_location="Ningbo",
                last_event_text="Booking Confirmed Ningbo — now",
                source_name="Mock Booking Feed",
                occurred_at=now,
            ),
        ]
    )
    db_session.commit()

    loaded_only = client.get("/api/bookings", params={"status": "loaded"}).json()
    assert [b["booking_number"] for b in loaded_only] == ["AAAA0000001"]

    confirmed_only = client.get("/api/bookings", params={"status": "booking_confirmed"}).json()
    assert [b["booking_number"] for b in confirmed_only] == ["BBBB0000002"]


def test_history_not_found_for_unknown_booking(client):
    resp = client.get("/api/bookings/UNKNOWN0001/history")
    assert resp.status_code == 404


def test_history_returns_empty_timeline_for_new_booking(client):
    _create(client)
    resp = client.get("/api/bookings/TCLU7788990/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["booking"]["booking_number"] == "TCLU7788990"
    assert body["timeline"] == []


def test_archive_then_remove_lifecycle(client):
    _create(client)

    archive_resp = client.post("/api/bookings/TCLU7788990/archive")
    assert archive_resp.status_code == 200
    assert archive_resp.json()["archived_at"] is not None

    # Already archived - re-archiving is rejected, same contract as vessels.
    assert client.post("/api/bookings/TCLU7788990/archive").status_code == 409

    # No longer shown in the active list, but still findable in the archived one.
    assert client.get("/api/bookings").json() == []
    archived = client.get("/api/bookings", params={"archived": "true"}).json()
    assert [b["booking_number"] for b in archived] == ["TCLU7788990"]

    remove_resp = client.delete("/api/bookings/TCLU7788990")
    assert remove_resp.status_code == 204
    assert client.get("/api/bookings/TCLU7788990/history").status_code == 404


def test_archive_unknown_booking_404s(client):
    assert client.post("/api/bookings/UNKNOWN0001/archive").status_code == 404


def test_remove_unknown_booking_404s(client):
    assert client.delete("/api/bookings/UNKNOWN0001").status_code == 404


def test_bookings_require_login(client):
    from fastapi.testclient import TestClient

    from app.main import app

    anon = TestClient(app)
    assert anon.get("/api/bookings").status_code == 401
    assert anon.post("/api/bookings", json={}).status_code == 401
