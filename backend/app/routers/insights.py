"""Phase 6 endpoints (Section 7): the AI voyage summary and the exception list.

Reachable by any logged-in user, not admin-only - these are operational views like the dashboard
and Reports, not configuration (see app/main.py's include_router call).
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ExceptionKind, Vessel, VesselException, VoyageSummary
from app.schemas import AiStatusOut, VesselExceptionOut, VoyageSummaryOut
from app.routers.history import _to_exception_out
from app.services import ai_service

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/ai-status", response_model=AiStatusOut)
def ai_status():
    """Whether AI voyage summaries are usable on this deployment. The frontend calls this to
    decide whether to show the "Generate AI Summary" button at all, rather than showing one that
    would always fail - the same pattern as GET /api/auth/microsoft/status."""
    return AiStatusOut(configured=ai_service.is_configured())


@router.get("/exceptions", response_model=list[VesselExceptionOut])
def list_exceptions(kind: ExceptionKind | None = None, limit: int = 200, db: Session = Depends(get_db)):
    """Recorded exceptions, newest first, optionally filtered to one kind (backing the Exceptions
    page's filter chips). Capped like the notification log is - this table only ever grows, so an
    uncapped query would eventually return everything a fleet has ever been flagged for.

    Exceptions for archived/removed vessels don't appear: archived vessels are skipped by the
    detector, and removing a vessel cascades its exceptions away with it (see models.py).
    """
    query = db.query(VesselException)
    if kind is not None:
        query = query.filter(VesselException.kind == kind)
    rows = query.order_by(VesselException.detected_at.desc()).limit(limit).all()
    return [_to_exception_out(exc) for exc in rows]


def _to_summary_out(summary: VoyageSummary, current_event_count: int) -> VoyageSummaryOut:
    """Attach staleness by comparing the event count the summary was written from against the
    vessel's current one - so a summary written before newer events landed is visibly out of
    date rather than quietly wrong."""
    return VoyageSummaryOut(
        summary=summary.summary,
        generated_at=summary.generated_at,
        source_event_count=summary.source_event_count,
        is_stale=current_event_count > summary.source_event_count,
    )


def _get_vessel_or_404(imo_number: str, db: Session) -> Vessel:
    vessel = db.query(Vessel).filter(Vessel.imo_number == imo_number).first()
    if vessel is None:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel


@router.get("/vessels/{imo_number}/summary", response_model=VoyageSummaryOut | None)
def get_voyage_summary(imo_number: str, db: Session = Depends(get_db)):
    """The cached AI voyage summary for a vessel, or null if none has been generated yet.

    Deliberately a *read* - it never generates on its own. Generation costs an API call, so it
    only happens when a user explicitly asks for one via the POST below; a page load never
    silently spends money.
    """
    vessel = _get_vessel_or_404(imo_number, db)
    if vessel.voyage_summary is None:
        return None
    return _to_summary_out(vessel.voyage_summary, len(vessel.events))


@router.post("/vessels/{imo_number}/summary", response_model=VoyageSummaryOut)
def generate_voyage_summary(imo_number: str, db: Session = Depends(get_db)):
    """Generate (or regenerate) the AI voyage summary for a vessel and cache it.

    Returns 503 when summaries are unavailable - no API key configured, or the model call
    failed - so the frontend can show a clear message rather than a broken panel, matching how
    PDF bulk-upload behaves without a key (routers/bulk_upload.py).
    """
    vessel = _get_vessel_or_404(imo_number, db)
    events = list(vessel.events)

    try:
        text = ai_service.generate_voyage_summary(vessel, events)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # One summary per vessel - overwrite in place rather than accumulating history, since a
    # superseded narrative of the same voyage has no value once a newer one exists.
    summary = vessel.voyage_summary
    if summary is None:
        summary = VoyageSummary(vessel_id=vessel.id, summary=text, source_event_count=len(events))
        db.add(summary)
    else:
        summary.summary = text
        summary.source_event_count = len(events)
        # Explicitly restamped: `generated_at`'s server_default only applies on insert, so
        # without this an updated summary would keep advertising its original timestamp.
        summary.generated_at = func.now()

    db.commit()
    db.refresh(summary)
    return _to_summary_out(summary, len(events))
