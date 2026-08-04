"""Admin-only tracking-source CRUD (Section 3.9), backing Settings → Tracking Sources. Gated at
the router-*inclusion* level in app/main.py (`Depends(require_admin)` passed to
`include_router`) rather than here, unlike routers/users.py which gates itself - both approaches
end up equally enforced, this one just happens to be wired up from the mounting side."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import TrackingSource
from app.schemas import TrackingSourceCreate, TrackingSourceOut, TrackingSourceUpdate

router = APIRouter(prefix="/api/tracking-sources", tags=["tracking-sources"])


@router.get("", response_model=list[TrackingSourceOut])
def list_tracking_sources(db: Session = Depends(get_db)):
    """List every catalogued source, including the "Not yet connected" real-website entries
    seeded at startup (see app/main.py's SEED_SOURCES) alongside the functional mock feed."""
    return db.query(TrackingSource).order_by(TrackingSource.name).all()


@router.post("", response_model=TrackingSourceOut, status_code=201)
def create_tracking_source(payload: TrackingSourceCreate, db: Session = Depends(get_db)):
    """Add a new source to the catalogue. Names must be unique. New sources default to
    `adapter_key="unavailable"` (see TrackingSourceCreate) since only the seeded mock adapter is
    actually wired up to poll anything - adding a source here doesn't make it start polling."""
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
    """Edit a source's fields, or flip its `enabled` toggle. Toggling the mock source's
    `enabled` flag is what actually pauses/resumes the simulated tracking updates - see
    services/tracking_worker.py's `mock_source_enabled` check."""
    source = db.query(TrackingSource).filter(TrackingSource.id == source_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Tracking source not found")

    # `exclude_unset=True` means only fields the client actually sent get applied - a PATCH
    # with just `{"enabled": false}` doesn't overwrite name/url/kind with defaults.
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(source, field, value)

    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=204)
def delete_tracking_source(source_id: int, db: Session = Depends(get_db)):
    """Remove a source from the catalogue entirely."""
    source = db.query(TrackingSource).filter(TrackingSource.id == source_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Tracking source not found")

    db.delete(source)
    db.commit()
    return None
