"""`EPIC-047H` - a read that raises is charged and paced like any other; a median above the ceiling is measured afresh."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_read_refresh import (
    RefreshOutcome,
    RefreshScope,
)

from .vps_feed_world import (
    LIMIT,
    SimulatedClock,
    SimulatedSource,
    SimulatedVenue,
    drive,
    refresher_for,
)

CEILING = int(LIMIT * 0.03)


class RaisingSource(SimulatedSource):
    """Spends what a facts read costs, then raises: the reader's own failure handling is gone."""

    def refresh(self, bot_id: str, scope: RefreshScope) -> RefreshOutcome:
        super().refresh(bot_id, scope)
        raise RuntimeError("the record step failed after the requests went out")


def test_a_read_that_raises_after_spending_is_charged_and_paced_not_retried_at_once() -> (
    None
):
    clock = SimulatedClock()
    venue = SimulatedVenue(clock)
    source = RaisingSource(venue, 5)
    refresher = refresher_for(source)

    drive(refresher, clock, 600)

    assert venue.worst_window() <= CEILING
    assert source.reads_of("facts") <= 600 / 12


def test_a_median_that_lands_above_the_ceiling_is_forgotten_and_the_kind_is_read_again() -> (
    None
):
    clock = SimulatedClock()
    venue = SimulatedVenue(clock)
    source = SimulatedSource(venue, 1, facts_cost=CEILING + 20)
    refresher = refresher_for(source)
    while source.reads_of("facts") < 3:
        drive(refresher, clock, 10)
    source.cost["facts"] = 20
    seen = source.reads_of("facts")

    drive(refresher, clock, 900)

    assert source.reads_of("facts") >= seen + 5
