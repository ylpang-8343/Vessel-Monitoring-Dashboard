"""Bulk vessel import (Section 3.2): Excel/CSV parsed directly, PDF via AI extraction. Always a
two-step flow - /preview returns rows for the user to review/correct in the frontend's editable
table, and only /import actually writes anything, so nothing is ever imported silently."""

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

# Recognised column headers for Excel/CSV uploads, so a template with either "IMO" or
# "IMO Number" (etc.) both map to the same internal field name.
COLUMN_ALIASES = {
    "vessel name": "name",
    "name": "name",
    "imo number": "imo_number",
    "imo": "imo_number",
    "destination port": "destination_port",
    "destination": "destination_port",
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename whatever columns the uploaded file has (via COLUMN_ALIASES) onto our internal
    field names, and make sure all three expected columns exist (as None) even if the file is
    missing one entirely - downstream code can then assume all three keys are always present."""
    df = df.rename(columns={c: COLUMN_ALIASES.get(str(c).strip().lower(), str(c)) for c in df.columns})
    for col in ("name", "imo_number", "destination_port"):
        if col not in df.columns:
            df[col] = None
    # pandas represents missing Excel/CSV cells as NaN, which isn't JSON-serialisable the way
    # None is - normalise all of them to None here, once, instead of downstream.
    df = df.where(pd.notnull(df), None)
    return df


def _validate_rows(raw_rows: list[dict], db: Session) -> list[BulkUploadRow]:
    """Classify every parsed/extracted row as ok/invalid/duplicate for the preview response.
    This is preview-time validation only - /import below re-validates duplicates itself rather
    than trusting that nothing changed between preview and import."""
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

        # Duplicate against both rows already seen earlier in *this* file and vessels already
        # in the database, so two rows with the same IMO in one upload don't both show "ok".
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
    """Parse an uploaded .xlsx/.csv/.pdf into rows for the frontend's editable preview table.
    Writes nothing to the database - see module docstring."""
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
            # extract_vessel_rows raises RuntimeError specifically when no API key is
            # configured - surface that as a clear "unavailable" response rather than a generic
            # 500, since Excel/CSV upload should keep working regardless.
            raise HTTPException(status_code=503, detail=str(exc))
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type — use .xlsx, .csv, or .pdf")

    return BulkUploadPreview(rows=_validate_rows(raw_rows, db))


@router.post("/import", response_model=BulkImportResult)
def import_bulk_rows(payload: BulkImportRequest, db: Session = Depends(get_db)):
    """Actually create vessels from rows the user has reviewed (and the frontend has already
    filtered down to status=="ok"). Still re-checks for duplicate IMOs here - both against each
    other within this request and against the database - since time may have passed since the
    preview was generated."""
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
