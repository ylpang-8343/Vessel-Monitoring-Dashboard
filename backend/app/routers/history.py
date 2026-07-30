from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vessel
from app.schemas import VesselHistoryOut
from app.services.presentation import to_vessel_out

router = APIRouter(prefix="/api/vessels", tags=["history"])


@router.get("/{imo_number}/history", response_model=VesselHistoryOut)
def get_vessel_history(imo_number: str, db: Session = Depends(get_db)):
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return VesselHistoryOut(vessel=to_vessel_out(vessel), timeline=list(vessel.events))
