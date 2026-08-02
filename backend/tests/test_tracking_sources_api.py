def test_list_includes_conftest_seeded_mock_source(admin_client):
    # main.py's own startup seeding (MarineTraffic/VesselFinder/Polestar GMDA) only runs
    # via the FastAPI lifespan, which a bare TestClient(app) doesn't trigger - only the
    # conftest-seeded mock source is guaranteed present here.
    names = {s["name"] for s in admin_client.get("/api/tracking-sources").json()}
    assert "Mock Tracking Feed" in names


def test_create_and_patch_and_delete_source(admin_client):
    resp = admin_client.post(
        "/api/tracking-sources",
        json={"name": "Test Source", "url": "https://example.com", "kind": "vessel", "adapter_key": "unavailable"},
    )
    assert resp.status_code == 201
    source = resp.json()
    assert source["enabled"] is False

    patch_resp = admin_client.patch(f"/api/tracking-sources/{source['id']}", json={"enabled": True})
    assert patch_resp.status_code == 200
    assert patch_resp.json()["enabled"] is True

    delete_resp = admin_client.delete(f"/api/tracking-sources/{source['id']}")
    assert delete_resp.status_code == 204

    remaining_ids = {s["id"] for s in admin_client.get("/api/tracking-sources").json()}
    assert source["id"] not in remaining_ids


def test_create_duplicate_name_rejected(admin_client):
    admin_client.post("/api/tracking-sources", json={"name": "Dup Source", "url": "https://example.com"})
    resp = admin_client.post("/api/tracking-sources", json={"name": "Dup Source", "url": "https://example.com"})
    assert resp.status_code == 409


def test_patch_unknown_source_404(admin_client):
    resp = admin_client.patch("/api/tracking-sources/999999", json={"enabled": True})
    assert resp.status_code == 404


def test_delete_unknown_source_404(admin_client):
    resp = admin_client.delete("/api/tracking-sources/999999")
    assert resp.status_code == 404


def test_non_admin_user_forbidden(client):
    resp = client.get("/api/tracking-sources")
    assert resp.status_code == 403


def test_unauthenticated_request_rejected():
    from fastapi.testclient import TestClient

    from app.main import app

    anon_client = TestClient(app)
    resp = anon_client.get("/api/tracking-sources")
    assert resp.status_code == 401
