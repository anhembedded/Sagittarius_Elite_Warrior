"""`EPIC-047H` - a closed gate delays the refresh and queues no burst; a failure is logged once per cause."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
)

from .vps_feed_world import (
    LIMIT,
    NO_METER,
    SimulatedClock,
    SimulatedSource,
    SimulatedVenue,
    drive,
    refresher_for,
)

CEILING = int(LIMIT * 0.03)
LOGGER = "App.Operations.VpsRefresh"


def test_nothing_is_read_while_the_gate_is_closed_to_routine_requests() -> None:
    clock = SimulatedClock()
    venue = SimulatedVenue(clock)
    source = SimulatedSource(venue, 5)
    refresher = refresher_for(source)
    drive(refresher, clock, 150)
    reads_before = len(source.calls)
    venue.closed_by_hand = True

    drive(refresher, clock, 400)

    assert len(source.calls) == reads_before


def test_reopening_the_gate_queues_no_burst_and_holds_the_ceiling() -> None:
    clock = SimulatedClock()
    venue = SimulatedVenue(clock)
    source = SimulatedSource(venue, 5)
    refresher = refresher_for(source)
    drive(refresher, clock, 150)
    venue.closed_by_hand = True
    drive(refresher, clock, 400)
    reopened = clock.seconds
    venue.closed_by_hand = False
    reads_at_reopening = len(source.calls)

    drive(refresher, clock, 120)

    after = [t for t, _, _ in source.calls[reads_at_reopening:]]
    assert after, "the refresh never resumed"
    # five overdue bots were spread over the interval again: not all of them in the first seconds.
    assert len([t for t in after if t < reopened + 10]) <= 2
    assert venue.worst_window(since=reopened - 1) <= CEILING


def test_a_failure_is_logged_once_per_cause_until_a_read_succeeds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = SimulatedClock()
    venue = SimulatedVenue(clock)
    source = SimulatedSource(venue, 1)
    source.failing["bot000"] = True
    refresher = refresher_for(source)

    with caplog.at_level("DEBUG", logger=LOGGER):
        drive(refresher, clock, 900)
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        source.failing["bot000"] = False
        drive(refresher, clock, 300)

    assert len(warnings) == 1
    assert "were not read" in warnings[0].message
    assert [r for r in caplog.records if "reading again" in r.message]


def test_a_venue_whose_weight_is_not_measured_is_not_read_and_says_so_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = SimulatedClock()
    source = SimulatedSource(SimulatedVenue(clock), 3)
    refresher = refresher_for(source, meter=NO_METER)

    with caplog.at_level("WARNING", logger=LOGGER):
        drive(refresher, clock, 600)

    assert source.calls == []
    assert len([r for r in caplog.records if "[unmeasured]" in r.message]) == 1


def test_the_refresh_set_to_zero_reads_nothing() -> None:
    clock = SimulatedClock()
    source = SimulatedSource(SimulatedVenue(clock), 3)

    drive(refresher_for(source, VpsFeedSettings.judged(0, 3.0, True)), clock, 600)

    assert source.calls == []
