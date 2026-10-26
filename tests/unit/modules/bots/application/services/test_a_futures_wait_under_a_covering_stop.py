"""`BUG-270` - a Futures bot whose protective stop covers its position waits out a dead price feed.

The incident: a Futures bot with a stop standing on the exchange was halted by `price_feed_stale`
and the halt cancelled its ladder and closed the position at market. On a Futures venue that reason
now recovers by itself (the rule of `rate_limited`'s kind: a dwell, three attempts in 24 h) **only
while a stop on the exchange covers the position**; the wait keeps the ladder and the stop, closes
nothing, and ends in the existing path (cancel the ladder, close at market) when the stop stops
covering, the attempts are used up, or the wait outlasts 15 minutes (the owner's limit).
Without a covering stop the halt is the one it always was.
"""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverage,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.covered_wait_world import (
    BEAT,
    COVERAGE_READ_EVERY,
    Protection,
    a_covered_world,
    beats,
    closing_orders,
    the_feed_dies,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.halt_recovery_world import (
    attempts_of,
)

S = BotLifecycleState


def test_a_covered_futures_bot_waits_and_keeps_its_ladder_and_closes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, marks = a_covered_world(Protection(StopCoverage.COVERED), monkeypatch)
    markets_before = len(closing_orders(world))

    ladder = the_feed_dies(world, marks)

    assert world.state() is S.AWAITING_RECOVERY
    assert world.runtime().reason is GridReason.PRICE_FEED_STALE
    assert len(world.book.open) == ladder, "the ladder rests on the exchange"
    assert len(closing_orders(world)) == markets_before, "nothing is closed at market"


@pytest.mark.parametrize(
    "coverage",
    [StopCoverage.UNCOVERED, StopCoverage.UNREAD, StopCoverage.NOTHING_EXPOSED],
    ids=lambda c: c.value,
)
def test_without_a_covering_stop_the_halt_still_closes_at_market(
    coverage: StopCoverage, monkeypatch: pytest.MonkeyPatch
) -> None:
    world, marks = a_covered_world(Protection(coverage), monkeypatch)
    markets_before = len(closing_orders(world))

    the_feed_dies(world, marks)

    assert world.state() is not S.AWAITING_RECOVERY
    assert world.book.open == {}, "the ladder is taken off"
    assert len(closing_orders(world)) > markets_before, (
        "the position is closed at market"
    )


def test_the_wait_recovers_by_itself_once_the_price_has_stayed_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, marks = a_covered_world(Protection(StopCoverage.COVERED), monkeypatch)
    the_feed_dies(world, marks)
    marks.unreadable = None

    beats(world, 130)

    assert world.state() is S.RUNNING
    assert attempts_of(world) == 1


def test_a_wait_whose_stop_stops_covering_ends_in_the_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protection = Protection(StopCoverage.COVERED)
    world, marks = a_covered_world(protection, monkeypatch)
    markets_before = len(closing_orders(world))
    the_feed_dies(world, marks)
    assert world.state() is S.AWAITING_RECOVERY
    protection.coverage = StopCoverage.UNCOVERED

    beats(world, COVERAGE_READ_EVERY)

    assert world.state() is not S.AWAITING_RECOVERY
    assert world.book.open == {}
    assert len(closing_orders(world)) > markets_before


def test_a_wait_outlasting_fifteen_minutes_ends_in_the_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world, marks = a_covered_world(Protection(StopCoverage.COVERED), monkeypatch)
    markets_before = len(closing_orders(world))
    the_feed_dies(world, marks)

    beats(world, 14 * 60)
    assert world.state() is S.AWAITING_RECOVERY
    assert len(closing_orders(world)) == markets_before

    beats(world, 2 * 60)

    assert world.state() is not S.AWAITING_RECOVERY
    assert world.book.open == {}
    assert len(closing_orders(world)) > markets_before


def test_a_waiting_bot_reads_its_coverage_once_in_three_beats_not_every_beat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wait's own reads cost the exchange 2 requests each, for every waiting bot: a third of
    them keeps a covered wait from being what closes the weight gate for the others, while the
    stop's presence is still looked at every beat (`ProtectiveStopService.supervise`)."""
    protection = Protection(StopCoverage.COVERED)
    world, marks = a_covered_world(protection, monkeypatch)
    the_feed_dies(world, marks)
    assert world.state() is S.AWAITING_RECOVERY
    reads_on_entry = protection.reads

    beats(world, 6 * BEAT)

    assert protection.reads - reads_on_entry == 2


def test_two_unreadable_reads_in_a_row_keep_the_wait_and_a_covered_read_forgets_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stop that cannot be read is not a covering stop, but one blip of the network the wait is
    for must not close a position: three reads in a row end the wait, a covered one in between
    starts the count again."""
    protection = Protection(StopCoverage.COVERED)
    world, marks = a_covered_world(protection, monkeypatch)
    the_feed_dies(world, marks)
    closes_before = len(closing_orders(world))

    protection.coverage = StopCoverage.UNREAD
    beats(world, 2 * COVERAGE_READ_EVERY)
    protection.coverage = StopCoverage.COVERED
    beats(world, COVERAGE_READ_EVERY)
    protection.coverage = StopCoverage.UNREAD
    beats(world, 2 * COVERAGE_READ_EVERY)

    assert world.state() is S.AWAITING_RECOVERY
    assert len(closing_orders(world)) == closes_before


def test_three_unreadable_reads_in_a_row_end_the_wait_in_the_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protection = Protection(StopCoverage.COVERED)
    world, marks = a_covered_world(protection, monkeypatch)
    the_feed_dies(world, marks)
    closes_before = len(closing_orders(world))

    protection.coverage = StopCoverage.UNREAD
    beats(world, 3 * COVERAGE_READ_EVERY)

    assert world.state() is not S.AWAITING_RECOVERY
    assert world.book.open == {}
    assert len(closing_orders(world)) > closes_before
