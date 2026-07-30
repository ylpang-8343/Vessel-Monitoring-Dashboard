from datetime import datetime, timezone

from app.models import EventType
from app.services.status_engine import derive_event_type, format_last_event_text
from app.sources.base import RawReport


def _report(event_kind: str, event_port: str, current_location: str | None = None) -> RawReport:
    return RawReport(
        vessel_imo="1234567",
        event_kind=event_kind,
        event_port=event_port,
        current_location=current_location or event_port,
        occurred_at=datetime(2026, 7, 25, 6, 0, tzinfo=timezone.utc),
        source_name="Mock Tracking Feed",
    )


def test_no_destination_departed_is_sailing():
    report = _report("departed", "Qingdao", current_location="South China Sea")
    assert derive_event_type(report, None) == EventType.SAILING


def test_no_destination_arrived_is_at_port():
    report = _report("arrived", "Singapore Anchorage")
    assert derive_event_type(report, None) == EventType.AT_PORT


def test_destination_set_departed_non_destination_is_eta():
    report = _report("departed", "Qingdao", current_location="South China Sea")
    assert derive_event_type(report, "Pasir Gudang") == EventType.ETA_DESTINATION


def test_arrived_at_matching_destination_is_arrived_destination():
    report = _report("arrived", "Pasir Gudang")
    assert derive_event_type(report, "Pasir Gudang") == EventType.ARRIVED_DESTINATION


def test_destination_match_is_case_insensitive_and_trims_whitespace():
    report = _report("arrived", "Pasir Gudang")
    assert derive_event_type(report, " pasir gudang ") == EventType.ARRIVED_DESTINATION


def test_departed_destination_is_sailed_from_destination():
    report = _report("departed", "Pasir Gudang", current_location="Johor Strait")
    assert derive_event_type(report, "Pasir Gudang") == EventType.SAILED_FROM_DESTINATION


def test_arrived_at_non_destination_port_is_at_port_even_with_destination_set():
    report = _report("arrived", "Singapore Anchorage")
    assert derive_event_type(report, "Pasir Gudang") == EventType.AT_PORT


def test_last_event_text_format():
    arrived = _report("arrived", "Pasir Gudang")
    assert format_last_event_text(arrived) == "Arrived Pasir Gudang — 25 Jul 2026, 06:00"

    departed = _report("departed", "Qingdao", current_location="South China Sea")
    assert format_last_event_text(departed) == "Sailed Qingdao — 25 Jul 2026, 06:00"
