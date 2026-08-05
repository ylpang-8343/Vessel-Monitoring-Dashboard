"""Background polling job for the Container/Booking Tracking module (Section 4) - the companion
to services/tracking_worker.py, same shape: on a fixed interval, ask the mock booking adapter for
updates on all active bookings and persist any new BookingEvent rows.

Runs on its own APScheduler instance (like report_worker.py's daily-report checker) rather than
sharing tracking_worker's, so a slow/stuck booking poll can never block vessel polling or vice
versa - the two modules are independent per the proposal's own "companion module" framing
(Section 4's opening line)."""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.db import SessionLocal
from app.models import Booking, BookingEvent, SourceKind, TrackingSource
from app.services.booking_status import format_last_event_text
from app.sources.mock_booking_adapter import MockBookingAdapter

logger = logging.getLogger("booking_worker")

# One adapter instance shared across every poll tick for the process's lifetime, so its
# per-booking simulated lifecycle step (see MockBookingAdapter._booking_step) persists between
# ticks instead of resetting each time - same rationale as tracking_worker's module-level _adapter.
_adapter = MockBookingAdapter()
_scheduler: BackgroundScheduler | None = None


def run_booking_poll() -> int:
    """One polling cycle: fetch active bookings, ask the mock adapter for new reports, and
    persist new BookingEvent rows. Gated on an enabled TrackingSource row with
    adapter_key="mock_booking" (kind=CONTAINER) - the same Settings → Tracking Sources
    enable/disable pattern tracking_worker.py uses for the vessel mock feed (Section 3.9), reused
    here rather than building a second admin screen just for this module (Section 4 explicitly
    calls for sharing patterns with the vessel dashboard)."""
    db = SessionLocal()
    try:
        mock_source_enabled = (
            db.query(TrackingSource)
            .filter(
                TrackingSource.adapter_key == "mock_booking",
                TrackingSource.kind == SourceKind.CONTAINER,
                TrackingSource.enabled.is_(True),
            )
            .first()
            is not None
        )
        if not mock_source_enabled:
            return 0

        bookings = db.query(Booking).filter(Booking.archived_at.is_(None)).all()
        if not bookings:
            return 0

        numbers = [b.booking_number for b in bookings]
        ports = {b.booking_number: (b.port_of_loading, b.port_of_discharge) for b in bookings}
        booking_by_number = {b.booking_number: b for b in bookings}

        reports = _adapter.poll(numbers, ports)
        created = 0
        for report in reports:
            booking = booking_by_number.get(report.booking_number)
            if booking is None:
                # Shouldn't normally happen (we only asked about bookings we just queried), but
                # guards against one being deleted mid-poll.
                continue
            event = BookingEvent(
                booking_id=booking.id,
                status=report.status,
                current_location=report.current_location,
                last_event_text=format_last_event_text(
                    report, booking.port_of_loading, booking.port_of_discharge
                ),
                source_name=report.source_name,
                occurred_at=report.occurred_at,
            )
            db.add(event)
            created += 1
        db.commit()
        logger.info("booking poll: recorded %d booking events", created)
        return created
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """Start the background poll job (idempotent). Runs `run_booking_poll` once immediately,
    then every `settings.tracking_poll_interval_seconds` - reusing the same interval setting as
    the vessel tracking worker rather than introducing a second one, since both are simulated
    feeds with no real rate limit to tune against yet. Called from app/main.py's startup
    lifespan."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_booking_poll,
        "interval",
        seconds=settings.tracking_poll_interval_seconds,
        id="booking_poll",
    )
    scheduler.start()
    scheduler.modify_job("booking_poll", next_run_time=datetime.now())
    _scheduler = scheduler
    return scheduler


def stop_scheduler() -> None:
    """Stop the background poll job. Called from app/main.py's shutdown lifespan; also
    monkeypatched to a no-op in tests (see tests/conftest.py)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
