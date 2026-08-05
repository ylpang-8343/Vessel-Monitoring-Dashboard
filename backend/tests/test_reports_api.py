def test_unauthenticated_request_rejected():
    from fastapi.testclient import TestClient

    from app.main import app

    anon_client = TestClient(app)
    assert anon_client.get("/api/reports/summary").status_code == 401


def test_regular_user_can_access_reports(client):
    # Unlike Settings/tracking-sources (Section 3.9) and notification config, Reports has no
    # admin gate - any logged-in user can view/export them.
    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] == []
    assert body["eta_to_destination"] == []
    assert body["arrived_at_destination"] == []
    assert "generated_at" in body


def test_summary_reflects_registered_vessels(client):
    client.post("/api/vessels", json={"name": "MV ABC", "imo_number": "1234567", "destination_port": "Pasir Gudang"})
    resp = client.get("/api/reports/summary")
    assert resp.status_code == 200
    assert len(resp.json()["active"]) == 1


def test_export_excel_returns_xlsx_content_type(client):
    resp = client.get("/api/reports/export.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "vessel-report.xlsx" in resp.headers["content-disposition"]
    assert resp.content[:2] == b"PK"


def test_export_pdf_returns_pdf_content_type(client):
    resp = client.get("/api/reports/export.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "vessel-report.pdf" in resp.headers["content-disposition"]
    assert resp.content.startswith(b"%PDF")
