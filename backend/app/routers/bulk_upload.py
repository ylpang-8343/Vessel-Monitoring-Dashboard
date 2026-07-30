import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vessel
from app.schemas import (
    BulkImportRequest,
    BulkImportResult,
    BulkUploadPreview,
    BulkUploadRow,
    VesselCreate,
)
from app.services.presentation import to_vessel_out
from app.services.pdf_extraction import extract_vessel_rows

router = APIRouter(prefix="/api/vessels/bulk", tags=["bulk-upload"])

COLUMN_ALIASES = {
    "vessel name": "name",
    "name": "name",
    "imo number": "imo_number",
    "imo": "imo_number",
    "destination port": "destination_port",
    "destination": "destination_port",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: COLUMN_ALIASES.get(str(c).strip().lower(), str(c)) for c in df.columns})
    for col in ("name", "imo_number", "destination_port"):
        if col not in df.columns:
            df[col] = None
    df = df.where(pd.notnull(df), None)
    return df


def _validate_rows(raw_rows: list[dict], db: Session) -> list[BulkUploadRow]:
    seen_imos: set[str] = set()
    results: list[BulkUploadRow] = []

    for i, raw in enumerate(raw_rows, start=1):
        name = (raw.get("name") or "").strip() or None
        imo = (raw.get("imo_number") or "").strip() or None
        destination = (raw.get("destination_port") or "").strip() or None

        if not name or not imo:
            results.append(
                BulkUploadRow(
                    row_number=i,
                    name=name,
                    imo_number=imo,
                    destination_port=destination,
                    status="invalid",
                    message="Missing vessel name or IMO number — please fill in manually before import",
                )
            )
            continue

        if not (imo.isdigit() and len(imo) == 7):
            results.append(
                BulkUploadRow(
                    row_number=i,
                    name=name,
                    imo_number=imo,
                    destination_port=destination,
                    status="invalid",
                    message="IMO number must be exactly 7 digits",
                )
            )
            continue

        if imo in seen_imos or db.query(Vessel).filter(Vessel.imo_number == imo).first():
            results.append(
                BulkUploadRow(
                    row_number=i,
                    name=name,
                    imo_number=imo,
                    destination_port=destination,
                    status="duplicate",
                    message=f"IMO {imo} already exists — skipped",
                )
            )
            continue

        seen_imos.add(imo)
        results.append(
            BulkUploadRow(
                row_number=i,
                name=name,
                imo_number=imo,
                destination_port=destination,
                status="ok",
            )
        )

    return results


@router.post("/preview", response_model=BulkUploadPreview)
async def preview_bulk_upload(file: UploadFile, db: Session = Depends(get_db)):
    filename = (file.filename or "").lower()
    content = await file.read()

    if filename.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content), dtype=str)
        raw_rows = _normalise_columns(df).to_dict(orient="records")
    elif filename.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(content), dtype=str)
        raw_rows = _normalise_columns(df).to_dict(orient="records")
    elif filename.endswith(".pdf"):
        try:
            raw_rows = extract_vessel_rows(content)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type — use .xlsx, .csv, or .pdf")

    return BulkUploadPreview(rows=_validate_rows(raw_rows, db))


@router.post("/import", response_model=BulkImportResult)
def import_bulk_rows(payload: BulkImportRequest, db: Session = Depends(get_db)):
    imported = []
    skipped = []
    seen_imos: set[str] = set()

    for i, row in enumerate(payload.rows, start=1):
        if row.imo_number in seen_imos or db.query(Vessel).filter(Vessel.imo_number == row.imo_number).first():
            skipped.append(
                BulkUploadRow(
                    row_number=i,
                    name=row.name,
                    imo_number=row.imo_number,
                    destination_port=row.destination_port,
                    status="duplicate",
                    message=f"IMO {row.imo_number} already exists — skipped",
                )
            )
            continue

        vessel = Vessel(name=row.name, imo_number=row.imo_number, destination_port=row.destination_port)
        db.add(vessel)
        seen_imos.add(row.imo_number)
        imported.append(vessel)

    db.commit()
    for v in imported:
        db.refresh(v)

    return BulkImportResult(imported=[to_vessel_out(v) for v in imported], skipped=skipped)
