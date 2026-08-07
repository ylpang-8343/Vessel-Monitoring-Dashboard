"""Vessel movement-history endpoint (Section 3.5), kept in its own router/file from
routers/vessels.py purely for organisation - it's mounted under the same `/api/vessels` prefix
and shares the same auth gating (see app/main.py)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Vessel, VesselException
from app.schemas import PredictedEtaOut, VesselExceptionOut, VesselHistoryOut
from app.services.predictive_eta import predict_arrival
from app.services.presentation import to_vessel_out

router = APIRouter(prefix="/api/vessels", tags=["history"])

# How many of a vessel's exceptions the history page shows. A vessel that is repeatedly late
# accrues one exception per voyage forever, so this page shows the current picture and defers
# the full list to /exceptions - without a cap, the alerts panel grows without bound and pushes
# the movement timeline (the reason for the page) off the screen.
MAX_HISTORY_EXCEPTIONS = 5


@router.get("/{imo_number}/history", response_model=VesselHistoryOut)
def get_vessel_history(imo_number: str, db: Session = Depends(get_db)):
    """Return a vessel plus its complete, oldest-first event timeline, together with Phase 6's
    predicted ETA and any exceptions recorded against it. Works the same whether the vessel is
    active or archived (Section 3.8 - "history stays available for reference"), since archiving
    only sets `archived_at` and never deletes anything."""
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")

    prediction = predict_arrival(vessel)
    predicted = (
        PredictedEtaOut(
            predicted_arrival=prediction.predicted_arrival,
            sample_size=prediction.sample_size,
            # Hours as a float rather than a raw timedelta - directly renderable by the
            # frontend without it having to parse a duration format. Kept to 4 decimal places
            # rather than 1: the simulated tracking feed completes a voyage within a single poll
            # tick, and rounding those to one decimal collapses them to a flat 0.0 that the UI
            # can only render as a misleading "0h". The frontend picks the display unit.
            typical_duration_hours=round(prediction.typical_duration.total_seconds() / 3600, 4),
            departed_from=prediction.departed_from,
            departed_at=prediction.departed_at,
        )
        if prediction is not None
        else None
    )

    exception_query = db.query(VesselException).filter(VesselException.vessel_id == vessel.id)
    exception_count = exception_query.count()
    recent_exceptions = (
        exception_query.order_by(VesselException.detected_at.desc()).limit(MAX_HISTORY_EXCEPTIONS).all()
    )

    return VesselHistoryOut(
        vessel=to_vessel_out(vessel),
        timeline=list(vessel.events),
        predicted_eta=predicted,
        exceptions=[_to_exception_out(exc) for exc in recent_exceptions],
        exception_count=exception_count,
    )


def _to_exception_out(exception: VesselException) -> VesselExceptionOut:
    """Flatten the vessel's name/IMO onto the exception so a caller rendering a list of them
    never needs a second lookup per row. Shared with routers/insights.py's Exceptions list."""
    return VesselExceptionOut(
        id=exception.id,
        vessel_name=exception.vessel.name,
        vessel_imo=exception.vessel.imo_number,
        kind=exception.kind,
        message=exception.message,
        detected_at=exception.detected_at,
    )
