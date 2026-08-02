from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_includes_conftest_seeded_mock_source():
    # main.py's own startup seeding (MarineTraffic/VesselFinder/Polestar GMDA) only runs
    # via the FastAPI lifespan, which a bare TestClient(app) doesn't trigger - only the
    # conftest-seeded mock source is guaranteed present here.
    names = {s["name"] for s in client.get("/api/tracking-sources").json()}
    assert "Mock Tracking Feed" in names


def test_create_and_patch_and_delete_source():
    resp = client.post(
        "/api/tracking-sources",
        json={"name": "Test Source", "url": "https://example.com", "kind": "vessel", "adapter_key": "unavailable"},
    )
    assert resp.status_code == 201
    source = resp.json()
    assert source["enabled"] is False

    patch_resp = client.patch(f"/api/tracking-sources/{source['id']}", json={"enabled": True})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["enabled"] is True

    delete_resp = client.delete(f"/api/tracking-sources/{source['id']}")
    assert delete_resp.status_code == 204

    remaining_ids = {s["id"] for s in client.get("/api/tracking-sources").json()}
    assert source["id"] not in remaining_ids


def test_create_duplicate_name_rejected():
    client.post("/api/tracking-sources", json={"name": "Dup Source", "url": "https://example.com"})
    resp = client.post("/api/tracking-sources", json={"name": "Dup Source", "url": "https://example.com"})
    assert resp.status_code == 409


def test_patch_unknown_source_404():
    resp = client.patch("/api/tracking-sources/999999", json={"enabled": True})
    assert resp.status_code == 404


def test_delete_unknown_source_404():
    resp = client.delete("/api/tracking-sources/999999")
    assert resp.status_code == 404
