"""`EPIC-047H` - the refresh holds its weight ceiling, whatever the number of bots (acceptance: a ceiling test that fails if the refresh exceeds it).

A fake clock and a fake exchange: the exchange charges the true cost of each read to the minute's used
weight and the refresher sees only the header. 3 % of a Futures minute is 72 weight.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.vps_feed_settings import (
    VpsFeedSettings,
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
RUN_SECONDS = 40 * 60


@pytest.mark.parametrize("bots", [1, 5, 20])
def test_the_weight_in_any_minute_stays_under_the_ceiling_at_1_5_and_20_bots(
    bots: int,
) -> None:
    clock = SimulatedClock()
    venue = SimulatedVenue(clock, background_per_minute=200)
    source = SimulatedSource(venue, bots)
    drive(refresher_for(source), clock, RUN_SECONDS)

    assert venue.refresh_spend, "the refresh never read anything"
    assert venue.worst_window() <= CEILING


def test_a_read_dearer_than_planned_lengthens_the_interval_and_never_overspends() -> (
    None
):
    clock = SimulatedClock()
    venue = SimulatedVenue(clock, background_per_minute=200)
    source = SimulatedSource(venue, 5, facts_cost=45)
    drive(refresher_for(source), clock, RUN_SECONDS)

    # Three reads find out what a read costs; from then on the expected cost is the dear one.
    assert venue.worst_window(since=600) <= CEILING
    assert venue.worst_window() <= CEILING + 3 * 45


def test_more_bots_stretch_the_interval_between_two_reads_of_one_bot() -> None:
    gaps = {}
    for bots in (1, 20):
        clock = SimulatedClock()
        venue = SimulatedVenue(clock)
        source = SimulatedSource(venue, bots)
        drive(refresher_for(source), clock, RUN_SECONDS)
        mine = [
            t for t, bot, scope in source.calls if bot == "bot000" and scope == "facts"
        ]
        gaps[bots] = (mine[-1] - mine[1]) / (len(mine) - 2)

    # One bot: the setting, plus the wait the slow round's dear reads (planner, fills) add under 72 a minute.
    assert 118 <= gaps[1] <= 140
    assert gaps[20] > 2 * gaps[1]


def test_a_setting_above_the_highest_ceiling_is_lowered_in_code() -> None:
    settings = VpsFeedSettings.judged(120, 80.0, True)

    assert settings.ceiling_pct == 10.0
    assert "above 10" in settings.notes[0]


def test_a_single_read_dearer_than_the_whole_ceiling_never_goes_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = SimulatedClock()
    venue = SimulatedVenue(clock)
    source = SimulatedSource(venue, 1, facts_cost=80)
    refresher = refresher_for(source, VpsFeedSettings.judged(120, 0.1, True))

    with caplog.at_level("WARNING", logger="App.Operations.VpsRefresh"):
        drive(refresher, clock, 10 * 60)

    assert source.reads_of("facts") + source.reads_of("full") == 0
    assert len([r for r in caplog.records if "[ceiling]" in r.message]) == 1
