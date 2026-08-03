def test_create_vessel_without_destination(client):
    resp = client.post("/api/vessels", json={"name": "MV ABC", "imo_number": "1234567"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "MV ABC"
    assert body["destination_port"] is None
    assert body["current_location"] is None


def test_create_vessel_with_destination(client):
    resp = client.post(
        "/api/vessels",
        json={"name": "MV Horizon Star", "imo_number": "9876543", "destination_port": "Port Klang West"},
    )
    assert resp.status_code == 201
    assert resp.json()["destination_port"] == "Port Klang West"


def test_rejects_non_7_digit_imo(client):
    resp = client.post("/api/vessels", json={"name": "MV Bad", "imo_number": "12345"})
    assert resp.status_code == 422


def test_rejects_duplicate_imo(client):
    client.post("/api/vessels", json={"name": "MV ABC", "imo_number": "2233445"})
    resp = client.post("/api/vessels", json={"name": "MV ABC Again", "imo_number": "2233445"})
    assert resp.status_code == 409


def test_list_vessels_search_by_name_imo_or_destination(client):
    client.post(
        "/api/vessels",
        json={"name": "MV Ocean Pearl", "imo_number": "4455667", "destination_port": "Pasir Gudang"},
    )
    client.post("/api/vessels", json={"name": "MV Northern Light", "imo_number": "7788990"})

    assert len(client.get("/api/vessels", params={"q": "Ocean"}).json()) == 1
    assert len(client.get("/api/vessels", params={"q": "4455667"}).json()) == 1
    assert len(client.get("/api/vessels", params={"q": "Pasir"}).json()) == 1
    assert len(client.get("/api/vessels", params={"q": "Northern"}).json()) == 1
    assert len(client.get("/api/vessels").json()) == 2


def test_list_vessels_filters_by_status(client, db_session):
    from datetime import datetime, timezone

    from app.models import EventType, StatusEvent, Vessel

    sailing = Vessel(name="MV Sailing", imo_number="1111111")
    at_port = Vessel(name="MV At Port", imo_number="2222222")
    db_session.add_all([sailing, at_port])
    db_session.commit()
    db_session.refresh(sailing)
    db_session.refresh(at_port)

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            StatusEvent(
                vessel_id=sailing.id,
                event_type=EventType.SAILING,
                current_location="South China Sea",
                last_event_text="Sailed Qingdao",
                source_name="Mock Tracking Feed",
                occurred_at=now,
            ),
            StatusEvent(
                vessel_id=at_port.id,
                event_type=EventType.AT_PORT,
                current_location="Singapore Anchorage",
                last_event_text="Arrived Singapore",
                source_name="Mock Tracking Feed",
                occurred_at=now,
            ),
        ]
    )
    db_session.commit()

    sailing_only = client.get("/api/vessels", params={"status": "sailing"}).json()
    assert [v["imo_number"] for v in sailing_only] == ["1111111"]

    at_port_only = client.get("/api/vessels", params={"status": "at_port"}).json()
    assert [v["imo_number"] for v in at_port_only] == ["2222222"]

    assert len(client.get("/api/vessels").json()) == 2


def test_history_not_found_for_unknown_imo(client):
    resp = client.get("/api/vessels/0000000/history")
    assert resp.status_code == 404


def test_history_returns_empty_timeline_for_new_vessel(client):
    client.post("/api/vessels", json={"name": "MV ABC", "imo_number": "1234567"})
    resp = client.get("/api/vessels/1234567/history")
    assert resp.status_code == 200
    body = resp.json()
    assert body["vessel"]["imo_number"] == "1234567"
    assert body["timeline"] == []
