"""Background polling job (Section 3.3): on a fixed interval, ask every enabled tracking-source
adapter for updates on all active vessels, and persist any new StatusEvent rows."""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db import SessionLocal
from app.models import StatusEvent, TrackingSource, Vessel
from app.services.archive_worker import run_archive_sweep
from app.services.status_engine import derive_event_type, format_last_event_text
from app.sources.mock_adapter import MockAdapter

logger = logging.getLogger("tracking_worker")

# One adapter instance shared across every poll tick for the process's lifetime, so its
# per-vessel simulated voyage state (see MockAdapter._vessel_state) persists between ticks
# instead of resetting each time.
_adapter = MockAdapter()
_scheduler: BackgroundScheduler | None = None


def run_tracking_poll() -> int:
    """One polling cycle: fetch vessels, ask each enabled adapter for new reports,
    run them through the status engine, and persist new StatusEvent rows.
    Only the mock adapter is wired up so far (see Section 3.9 / plan for the
    pluggable-adapter rationale) - gated on an enabled "mock" TrackingSource row so the
    admin settings screen's enable/disable toggle actually pauses/resumes updates (3.9).
    Archived vessels (3.7/3.8) are excluded. The arrived-at-destination retention sweep
    (3.7) runs *before* polling, not after: polling always advances every active vessel by
    one step (see mock_adapter.py), so if the sweep ran after polling it would never see a
    vessel still sitting at ARRIVED_DESTINATION from a prior tick - this tick's own poll
    would have already moved it on first. Running the sweep first means a vessel that has
    aged past the retention window gets archived - and excluded from `vessels` below -
    before this tick's poll ever touches it."""
    db = SessionLocal()
    try:
        mock_source_enabled = (
            db.query(TrackingSource)
            .filter(TrackingSource.adapter_key == "mock", TrackingSource.enabled.is_(True))
            .first()
            is not None
        )
        if not mock_source_enabled:
            # Admin has disabled (or removed) the mock source - skip this tick entirely,
            # including the archive sweep, so nothing changes while tracking is paused.
            return 0

        run_archive_sweep(db)

        vessels = db.query(Vessel).filter(Vessel.archived_at.is_(None)).all()
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
                # Shouldn't normally happen (we only asked about vessels we just queried), but
                # guards against a vessel being deleted mid-poll.
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
    """Start the background poll job (idempotent - calling it again while already running just
    returns the existing scheduler). Runs `run_tracking_poll` once immediately, then every
    `settings.tracking_poll_interval_seconds`. Called from app/main.py's startup lifespan."""
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
    # Without this, APScheduler would wait a full interval before the very first run - fire
    # one immediately so a freshly-started backend doesn't sit with stale/empty data for
    # minutes before the first poll happens.
    scheduler.modify_job("tracking_poll", next_run_time=datetime.now())
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    """Stop the background poll job. Called from app/main.py's shutdown lifespan; also
    monkeypatched to a no-op in tests (see tests/conftest.py) since tests don't want a live
    background thread polling against their throwaway test database."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
