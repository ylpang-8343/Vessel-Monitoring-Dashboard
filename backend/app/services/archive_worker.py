"""Implements the auto-archive half of Section 3.7: once a vessel's latest tracked event is
"Arrived at Destination", it stays visible for a configurable retention window (default 10 days,
Section 3.7) before being automatically archived. Vessels without a destination never produce an
ARRIVED_DESTINATION event (see status_engine.py), so this never touches them, matching 3.1/3.7's
"if no destination was set, none of this applies" rule.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models import EventType, Vessel


def _as_naive_utc(value: datetime) -> datetime:
    # SQLite (used in tests) drops tzinfo on round-trip even for DateTime(timezone=True)
    # columns, while Postgres preserves it - normalize to naive UTC so comparisons work
    # against either backend.
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def run_archive_sweep(db: Session, retention_days: int | None = None) -> int:
    """Archive every active vessel whose latest event is ARRIVED_DESTINATION and has sat there
    longer than the retention window. Called automatically on every tracking-poll tick (see
    services/tracking_worker.py) - there is no separate schedule or API endpoint for it.

    `retention_days` defaults to `settings.arrived_retention_days`; tests (and, briefly, manual
    verification passes) can override it to make the sweep's effect observable immediately
    instead of waiting real days.

    Returns the number of vessels archived, mostly for logging/test assertions.
    """
    retention = timedelta(days=retention_days if retention_days is not None else settings.arrived_retention_days)
    cutoff = _as_naive_utc(datetime.now(timezone.utc)) - retention

    archived = 0
    vessels = db.query(Vessel).filter(Vessel.archived_at.is_(None)).all()
    for vessel in vessels:
        latest = vessel.events[-1] if vessel.events else None
        if latest is None or latest.event_type != EventType.ARRIVED_DESTINATION:
            continue
        if _as_naive_utc(latest.occurred_at) <= cutoff:
            vessel.archived_at = datetime.now(timezone.utc)
            archived += 1

    if archived:
        db.commit()
    return archived
