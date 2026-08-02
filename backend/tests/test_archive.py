def _register(client, name="MV ABC", imo="1234567", destination=None):
    payload = {"name": name, "imo_number": imo}
    if destination:
        payload["destination_port"] = destination
    resp = client.post("/api/vessels", json=payload)
    assert resp.status_code == 201
    return resp.json()


def test_archive_hides_vessel_from_default_list_and_shows_under_archived(client):
    _register(client)
    resp = client.post("/api/vessels/1234567/archive")
    assert resp.status_code == 200
    assert resp.json()["archived_at"] is not None

    active = client.get("/api/vessels").json()
    assert all(v["imo_number"] != "1234567" for v in active)

    archived = client.get("/api/vessels", params={"archived": True}).json()
    assert any(v["imo_number"] == "1234567" for v in archived)


def test_archive_unknown_vessel_404(client):
    resp = client.post("/api/vessels/0000000/archive")
    assert resp.status_code == 404


def test_archive_already_archived_409(client):
    _register(client)
    client.post("/api/vessels/1234567/archive")
    resp = client.post("/api/vessels/1234567/archive")
    assert resp.status_code == 409


def test_remove_vessel_deletes_it_and_its_history(client):
    _register(client)
    resp = client.delete("/api/vessels/1234567")
    assert resp.status_code == 204

    assert client.get("/api/vessels/1234567/history").status_code == 404
    active = client.get("/api/vessels").json()
    assert all(v["imo_number"] != "1234567" for v in active)


def test_remove_unknown_vessel_404(client):
    resp = client.delete("/api/vessels/0000000")
    assert resp.status_code == 404


def test_archived_vessel_history_still_viewable(client):
    _register(client)
    client.post("/api/vessels/1234567/archive")
    resp = client.get("/api/vessels/1234567/history")
    assert resp.status_code == 200
    assert resp.json()["vessel"]["archived_at"] is not None
