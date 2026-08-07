"""Shared datetime normalisation for comparing stored timestamps against `now`.

Extracted here because Postgres and SQLite disagree about timezone awareness on round-trip:
Postgres preserves tzinfo on a `DateTime(timezone=True)` column, SQLite (used by the test suite)
drops it. Comparing a naive value from one against an aware value from the other raises
TypeError, so every module that does "is this stored timestamp older than X" arithmetic has to
normalise first - services/archive_worker.py (Section 3.7's retention sweep) and
services/exception_detector.py (Phase 6's delay/long-stay thresholds) both do.
"""

from datetime import datetime, timezone


def as_naive_utc(value: datetime) -> datetime:
    """Return `value` as a naive UTC datetime, converting from whatever offset it carries.
    Already-naive values are assumed to be UTC and returned unchanged."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def utc_now_naive() -> datetime:
    """`datetime.now(UTC)` in the same naive-UTC shape as `as_naive_utc`, so the two are always
    directly comparable."""
    return as_naive_utc(datetime.now(timezone.utc))
