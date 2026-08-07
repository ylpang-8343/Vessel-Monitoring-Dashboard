from datetime import datetime, timedelta, timezone

from app.models import EventType, StatusEvent, Vessel
from app.services.predictive_eta import predict_arrival

BASE = datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc)


def _event(event_type: EventType, offset_hours: float, location: str) -> StatusEvent:
    return StatusEvent(
        event_type=event_type,
        current_location=location,
        last_event_text=f"{event_type.value} {location}",
        source_name="Mock Tracking Feed",
        occurred_at=BASE + timedelta(hours=offset_hours),
    )


def _vessel(events: list[StatusEvent], destination: str | None = "Pasir Gudang") -> Vessel:
    vessel = Vessel(name="MV Predict", imo_number="1234567", destination_port=destination)
    vessel.events = events
    return vessel


def test_no_prediction_without_a_destination():
    vessel = _vessel([_event(EventType.SAILING, 0, "South China Sea")], destination=None)
    assert predict_arrival(vessel) is None


def test_no_prediction_when_not_currently_underway():
    # Sitting at port, not en route - there is no in-progress voyage to predict the end of.
    vessel = _vessel([_event(EventType.AT_PORT, 0, "Singapore Anchorage")])
    assert predict_arrival(vessel) is None


def test_no_prediction_without_a_completed_prior_voyage():
    # First ever voyage: underway, but no history to average over. Returning None here rather
    # than inventing a number is the point - see the module docstring.
    vessel = _vessel([_event(EventType.ETA_DESTINATION, 0, "Qingdao")])
    assert predict_arrival(vessel) is None


def test_predicts_from_the_median_of_completed_voyages():
    events = [
        # Voyage 1: 10 hours.
        _event(EventType.ETA_DESTINATION, 0, "Qingdao"),
        _event(EventType.ARRIVED_DESTINATION, 10, "Pasir Gudang"),
        # Voyage 2: 20 hours.
        _event(EventType.ETA_DESTINATION, 30, "Qingdao"),
        _event(EventType.ARRIVED_DESTINATION, 50, "Pasir Gudang"),
        # Voyage 3: 30 hours.
        _event(EventType.ETA_DESTINATION, 70, "Qingdao"),
        _event(EventType.ARRIVED_DESTINATION, 100, "Pasir Gudang"),
        # Current voyage, still underway.
        _event(EventType.ETA_DESTINATION, 120, "Qingdao"),
    ]
    prediction = predict_arrival(_vessel(events))

    assert prediction is not None
    assert prediction.sample_size == 3
    # Median of 10h / 20h / 30h is 20h, applied to the current departure at +120h.
    assert prediction.typical_duration == timedelta(hours=20)
    assert prediction.predicted_arrival == BASE + timedelta(hours=140)
    assert prediction.departed_from == "Qingdao"


def test_median_ignores_one_freak_voyage():
    # The whole reason for median over mean: a single 500-hour outlier must not drag the
    # prediction with it.
    events = [
        _event(EventType.ETA_DESTINATION, 0, "Qingdao"),
        _event(EventType.ARRIVED_DESTINATION, 10, "Pasir Gudang"),
        _event(EventType.ETA_DESTINATION, 20, "Qingdao"),
        _event(EventType.ARRIVED_DESTINATION, 520, "Pasir Gudang"),  # 500h outlier
        _event(EventType.ETA_DESTINATION, 530, "Qingdao"),
        _event(EventType.ARRIVED_DESTINATION, 542, "Pasir Gudang"),  # 12h
        _event(EventType.ETA_DESTINATION, 560, "Qingdao"),
    ]
    prediction = predict_arrival(_vessel(events))

    assert prediction is not None
    # Median of 10h / 500h / 12h is 12h; the mean would have been ~174h.
    assert prediction.typical_duration == timedelta(hours=12)


def test_incomplete_legs_are_not_counted_as_voyages():
    events = [
        # A departure that never reached the destination (vessel diverted to a port call).
        _event(EventType.ETA_DESTINATION, 0, "Qingdao"),
        _event(EventType.AT_PORT, 5, "Singapore Anchorage"),
        # One genuinely completed voyage.
        _event(EventType.ETA_DESTINATION, 10, "Qingdao"),
        _event(EventType.ARRIVED_DESTINATION, 25, "Pasir Gudang"),
        # Current voyage.
        _event(EventType.ETA_DESTINATION, 40, "Qingdao"),
    ]
    prediction = predict_arrival(_vessel(events))

    assert prediction is not None
    assert prediction.sample_size == 1
    assert prediction.typical_duration == timedelta(hours=15)
