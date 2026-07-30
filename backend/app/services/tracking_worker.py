import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db import SessionLocal
from app.models import StatusEvent, Vessel
from app.services.status_engine import derive_event_type, format_last_event_text
from app.sources.mock_adapter import MockAdapter

logger = logging.getLogger("tracking_worker")

_adapter = MockAdapter()
_scheduler: BackgroundScheduler | None = None


def run_tracking_poll() -> int:
    """One polling cycle: fetch vessels, ask each enabled adapter for new reports,
    run them through the status engine, and persist new StatusEvent rows.
    Only the mock adapter is wired up in Phase 1 (see Section 3.9 / plan for the
    pluggable-adapter rationale)."""
    db = SessionLocal()
    try:
        vessels = db.query(Vessel).all()
        if not vessels:
            return 0

        imos = [v.imo_number for v in vessels]
        destinations = {v.imo_number: v.destination_port for v in vessels}
        vessel_by_imo = {v.imo_number: v for v in vessels}

        reports = _adapter.poll(imos, destinations)
        created = 0
        for report in reports:
            vessel = vessel_by_imo.get(report.vessel_imo)
            if vessel is None:
                continue
            event_type = derive_event_type(report, vessel.destination_port)
            event = StatusEvent(
                vessel_id=vessel.id,
                event_type=event_type,
                current_location=report.current_location,
                last_event_text=format_last_event_text(report),
                source_name=report.source_name,
                occurred_at=report.occurred_at,
            )
            db.add(event)
            created += 1
        db.commit()
        logger.info("tracking poll: recorded %d status events", created)
        return created
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_tracking_poll,
        "interval",
        seconds=settings.tracking_poll_interval_seconds,
        id="tracking_poll",
    )
    scheduler.start()
    scheduler.modify_job("tracking_poll", next_run_time=datetime.now())
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
