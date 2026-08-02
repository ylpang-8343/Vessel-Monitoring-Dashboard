from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import TrackingSource
from app.schemas import TrackingSourceCreate, TrackingSourceOut, TrackingSourceUpdate

router = APIRouter(prefix="/api/tracking-sources", tags=["tracking-sources"])


@router.get("", response_model=list[TrackingSourceOut])
def list_tracking_sources(db: Session = Depends(get_db)):
    return db.query(TrackingSource).order_by(TrackingSource.name).all()


@router.post("", response_model=TrackingSourceOut, status_code=201)
def create_tracking_source(payload: TrackingSourceCreate, db: Session = Depends(get_db)):
    existing = db.query(TrackingSource).filter(TrackingSource.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"A source named '{payload.name}' already exists")

    source = TrackingSource(
        name=payload.name,
        url=payload.url,
        kind=payload.kind,
        adapter_key=payload.adapter_key,
        enabled=payload.enabled,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/{source_id}", response_model=TrackingSourceOut)
def update_tracking_source(source_id: int, payload: TrackingSourceUpdate, db: Session = Depends(get_db)):
    source = db.query(TrackingSource).filter(TrackingSource.id == source_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Tracking source not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(source, field, value)

    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=204)
def delete_tracking_source(source_id: int, db: Session = Depends(get_db)):
    source = db.query(TrackingSource).filter(TrackingSource.id == source_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Tracking source not found")

    db.delete(source)
    db.commit()
    return None
