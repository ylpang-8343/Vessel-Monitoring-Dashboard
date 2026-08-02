from app.sources.mock_adapter import DWELL_TICKS, MockAdapter


def _poll_once(adapter, imo, destinations):
    reports = adapter.poll([imo], destinations)
    return reports[0] if reports else None


def test_full_voyage_cycle_does_not_duplicate_the_reset_departure():
    # Regression test: the cycle-reset branch used to set state["step"] = -1, which the
    # trailing `state["step"] += 1` turned into 0 - not 1 - so the tick immediately after a
    # new voyage's first "departed" report re-executed the step==0 branch again instead of
    # advancing to "arrived", re-emitting an identical "departed <same origin>" report twice
    # in a row (visible in the vessel history as two consecutive identical "Sailed X" lines).
    adapter = MockAdapter()
    imo = "1234567"
    destinations = {imo: "Pasir Gudang"}

    depart_origin = _poll_once(adapter, imo, destinations)
    arrive_destination = _poll_once(adapter, imo, destinations)
    for _ in range(DWELL_TICKS):
        assert _poll_once(adapter, imo, destinations) is None  # dwelling, no report
    depart_destination = _poll_once(adapter, imo, destinations)
    cycle_reset_depart = _poll_once(adapter, imo, destinations)
    next_after_reset = _poll_once(adapter, imo, destinations)

    assert depart_origin.event_kind == "departed"
    assert arrive_destination.event_kind == "arrived"
    assert depart_destination.event_kind == "departed"
    assert depart_destination.event_port == "Pasir Gudang"
    assert cycle_reset_depart.event_kind == "departed"

    # This is the regression check: previously this was ALSO "departed" with the same
    # event_port as cycle_reset_depart (a duplicate), instead of advancing to "arrived".
    assert next_after_reset.event_kind == "arrived"


def test_cycle_reset_leaves_step_at_one_not_zero():
    adapter = MockAdapter()
    imo = "1234567"
    destinations = {imo: "Pasir Gudang"}

    # depart origin, arrive destination, dwell x DWELL_TICKS, depart destination,
    # cycle-reset depart -> lands right after the reset tick.
    for _ in range(4 + DWELL_TICKS):
        adapter.poll([imo], destinations)

    assert adapter._vessel_state[imo]["step"] == 1
