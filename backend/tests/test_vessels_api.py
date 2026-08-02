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
