import io


def _csv_file(content: str) -> dict:
    return {"file": ("vessels.csv", io.BytesIO(content.encode()), "text/csv")}


def test_preview_csv_flags_valid_duplicate_and_invalid_rows(client):
    client.post("/api/vessels", json={"name": "MV Existing", "imo_number": "4455667"})

    csv_content = (
        "Vessel Name,IMO Number,Destination Port\n"
        "MV ABC,1234567,Pasir Gudang\n"
        "MV Existing,4455667,\n"
        "MV Bad,12345,\n"
    )
    resp = client.post("/api/vessels/bulk/preview", files=_csv_file(csv_content))
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert rows[0]["status"] == "ok"
    assert rows[0]["destination_port"] == "Pasir Gudang"
    assert rows[1]["status"] == "duplicate"
    assert rows[2]["status"] == "invalid"


def test_preview_rejects_unsupported_file_type(client):
    resp = client.post(
        "/api/vessels/bulk/preview", files={"file": ("vessels.txt", io.BytesIO(b"MV ABC"), "text/plain")}
    )
    assert resp.status_code == 400


def test_import_inserts_valid_rows_and_skips_duplicates(client):
    client.post("/api/vessels", json={"name": "MV Existing", "imo_number": "4455667"})

    resp = client.post(
        "/api/vessels/bulk/import",
        json={
            "rows": [
                {"name": "MV ABC", "imo_number": "1234567", "destination_port": "Pasir Gudang"},
                {"name": "MV Existing", "imo_number": "4455667"},
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["imported"]) == 1
    assert body["imported"][0]["imo_number"] == "1234567"
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["status"] == "duplicate"


def test_pdf_preview_without_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", None)
    resp = client.post(
        "/api/vessels/bulk/preview", files={"file": ("vessels.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")}
    )
    assert resp.status_code == 503
