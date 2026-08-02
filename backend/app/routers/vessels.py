from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vessel
from app.schemas import VesselCreate, VesselOut
from app.services.presentation import to_vessel_out

router = APIRouter(prefix="/api/vessels", tags=["vessels"])


@router.get("", response_model=list[VesselOut])
def list_vessels(q: str | None = None, archived: bool = False, db: Session = Depends(get_db)):
    query = db.query(Vessel)
    query = query.filter(Vessel.archived_at.isnot(None)) if archived else query.filter(Vessel.archived_at.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Vessel.name.ilike(like),
                Vessel.imo_number.ilike(like),
                Vessel.destination_port.ilike(like),
            )
        )
    vessels = query.order_by(Vessel.name).all()
    return [to_vessel_out(v) for v in vessels]


@router.post("", response_model=VesselOut, status_code=201)
def create_vessel(payload: VesselCreate, db: Session = Depends(get_db)):
    existing = db.query(Vessel).filter(Vessel.imo_number == payload.imo_number).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"IMO {payload.imo_number} is already registered")

    vessel = Vessel(
        name=payload.name,
        imo_number=payload.imo_number,
        destination_port=payload.destination_port,
    )
    db.add(vessel)
    db.commit()
    db.refresh(vessel)
    return to_vessel_out(vessel)


@router.post("/{imo_number}/archive", response_model=VesselOut)
def archive_vessel(imo_number: str, db: Session = Depends(get_db)):
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    if vessel.archived_at is not None:
        raise HTTPException(status_code=409, detail=f"Vessel {imo_number} is already archived")

    vessel.archived_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(vessel)
    return to_vessel_out(vessel)


@router.delete("/{imo_number}", status_code=204)
def remove_vessel(imo_number: str, db: Session = Depends(get_db)):
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")

    db.delete(vessel)
    db.commit()
    return None
