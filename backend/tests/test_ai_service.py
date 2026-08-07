from datetime import datetime, timezone

import pytest

from app.models import EventType, StatusEvent, Vessel
from app.services import ai_service


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Response:
    def __init__(self, text="MV Test departed Qingdao on 01 Jul and arrived Pasir Gudang on 03 Jul.", stop_reason="end_turn"):
        self.content = [_Block(text)] if text else []
        self.stop_reason = stop_reason


def _vessel_with_events():
    vessel = Vessel(name="MV Test", imo_number="1234567", destination_port="Pasir Gudang")
    vessel.events = [
        StatusEvent(
            event_type=EventType.ETA_DESTINATION,
            current_location="South China Sea",
            last_event_text="Sailed Qingdao — 01 Jul 2026, 08:00",
            source_name="Mock Tracking Feed",
            occurred_at=datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc),
        ),
        StatusEvent(
            event_type=EventType.ARRIVED_DESTINATION,
            current_location="Pasir Gudang",
            last_event_text="Arrived Pasir Gudang — 03 Jul 2026, 14:00",
            source_name="Mock Tracking Feed",
            occurred_at=datetime(2026, 7, 3, 14, 0, tzinfo=timezone.utc),
        ),
    ]
    return vessel


def test_unavailable_without_an_api_key(monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", None)
    assert ai_service.is_configured() is False

    vessel = _vessel_with_events()
    with pytest.raises(RuntimeError, match="not configured"):
        ai_service.generate_voyage_summary(vessel, vessel.events)


def test_configured_once_a_key_is_set(monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")
    assert ai_service.is_configured() is True


def test_rejects_a_vessel_with_no_events(monkeypatch):
    # Nothing to narrate - fail clearly rather than calling the model on an empty timeline.
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")
    vessel = Vessel(name="MV Fresh", imo_number="7654321", destination_port=None)
    vessel.events = []

    with pytest.raises(RuntimeError, match="no tracking events"):
        ai_service.generate_voyage_summary(vessel, [])


def test_returns_the_models_narrative(monkeypatch):
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")
    captured = {}

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response()

    class _Client:
        def __init__(self, api_key=None):
            self.messages = _Messages()

    monkeypatch.setattr("app.services.ai_service.Anthropic", _Client)

    vessel = _vessel_with_events()
    summary = ai_service.generate_voyage_summary(vessel, vessel.events)

    assert summary.startswith("MV Test departed Qingdao")
    # The timeline actually reaches the model - a summary built from anything other than the
    # stored events would be inventing facts.
    prompt = captured["messages"][0]["content"]
    assert "MV Test" in prompt and "IMO 1234567" in prompt
    assert "Arrived Pasir Gudang — 03 Jul 2026, 14:00" in prompt
    assert captured["model"] == "claude-opus-5"


def test_api_failure_becomes_a_clear_runtime_error(monkeypatch):
    import httpx
    from anthropic import APIConnectionError

    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")

    class _Messages:
        def create(self, **kwargs):
            raise APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    class _Client:
        def __init__(self, api_key=None):
            self.messages = _Messages()

    monkeypatch.setattr("app.services.ai_service.Anthropic", _Client)

    vessel = _vessel_with_events()
    with pytest.raises(RuntimeError, match="Could not generate the summary"):
        ai_service.generate_voyage_summary(vessel, vessel.events)


def test_a_model_refusal_is_surfaced_not_returned_as_a_summary(monkeypatch):
    # A declined request returns HTTP 200 with empty/partial content - reading content[0]
    # blindly would hand the user an empty "summary".
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "test-key")

    class _Messages:
        def create(self, **kwargs):
            return _Response(text="", stop_reason="refusal")

    class _Client:
        def __init__(self, api_key=None):
            self.messages = _Messages()

    monkeypatch.setattr("app.services.ai_service.Anthropic", _Client)

    vessel = _vessel_with_events()
    with pytest.raises(RuntimeError, match="declined"):
        ai_service.generate_voyage_summary(vessel, vessel.events)
