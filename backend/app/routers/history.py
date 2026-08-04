"""Vessel movement-history endpoint (Section 3.5), kept in its own router/file from
routers/vessels.py purely for organisation - it's mounted under the same `/api/vessels` prefix
and shares the same auth gating (see app/main.py)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vessel
from app.schemas import VesselHistoryOut
from app.services.presentation import to_vessel_out

router = APIRouter(prefix="/api/vessels", tags=["history"])


@router.get("/{imo_number}/history", response_model=VesselHistoryOut)
def get_vessel_history(imo_number: str, db: Session = Depends(get_db)):
    """Return a vessel plus its complete, oldest-first event timeline. Works the same whether
    the vessel is active or archived (Section 3.8 - "history stays available for reference"),
    since archiving only sets `archived_at` and never deletes anything."""
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return VesselHistoryOut(vessel=to_vessel_out(vessel), timeline=list(vessel.events))
