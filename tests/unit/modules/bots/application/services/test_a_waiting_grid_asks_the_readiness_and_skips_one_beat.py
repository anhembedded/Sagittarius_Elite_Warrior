"""`EPIC-044B` - what a Grid waiting for its range asks at entry, and the range-exit close after it.

ADR 044 D5 and D7: at the price that enters the range the bot asks the readiness the Bots screen
shows (the balance, the plan's verdicts) and halts on a refusal of the plan or keeps waiting when the
venue could not be read; after an entry the range-exit close of a position-venue bot skips exactly
one mark beat, so a mark on a bound cannot open the position and close it at market in two beats.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_entry_readiness import (
    EntryReadiness,
    IEntryReadiness,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.waiting_world import (
    BELOW,
    INSIDE,
    WITH_NO_EXITS,
    Wait,
    a_wait,
    started,
)

D = Decimal
S = BotLifecycleState


class _Judge(IEntryReadiness):
    """The entry judge, saying what the test says."""

    def __init__(self, answer: EntryReadiness) -> None:
        self.answer = answer
        self.asked = 0

    def judge(self, bot: Bot) -> EntryReadiness:
        self.asked += 1
        return self.answer


def test_a_plan_the_readiness_refuses_at_entry_halts_the_bot_with_the_screens_words() -> (
    None
):
    """The balance and the plan's verdicts, judged at the price now: nothing is placed."""
    judge = _Judge(
        EntryReadiness("1 thing left: the account holds 40 USDT, the ladder needs 1000")
    )
    world = grid_world(last_price=BELOW, config=WITH_NO_EXITS, entry_readiness=judge)
    case = started(Wait(world, None))

    case.price_is(INSIDE)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.ENTRY_REFUSED
    assert "the account holds 40 USDT" in world.runtime().reason_detail
    assert world.book.requests == []


def test_a_readiness_that_could_not_read_the_venue_keeps_the_bot_waiting_and_asks_later() -> (
    None
):
    judge = _Judge(EntryReadiness("the account could not be read", transient=True))
    world = grid_world(last_price=BELOW, config=WITH_NO_EXITS, entry_readiness=judge)
    case = started(Wait(world, None))

    case.price_is(INSIDE)
    assert world.state() is S.AWAITING_RANGE
    assert judge.asked == 1

    world.monotonic.advance(10)
    case.price_is(INSIDE)
    assert judge.asked == 1, "a deferred entry waits before it asks the account again"

    judge.answer = EntryReadiness()
    world.monotonic.advance(60)
    case.price_is(INSIDE)

    assert world.state() is S.RUNNING


def a_futures_wait_that_closes_on_exit(price: Decimal) -> Wait:
    config = {**WITH_NO_EXITS, "on_range_exit": "close"}
    return started(a_wait("futures", "LONG", price, config=config))


def test_a_range_exit_close_skips_exactly_one_beat_after_entry() -> None:
    """Entry at the bound, the mark then leaves and stays out: the first beat after the ladder is
    laid is not judged, the second is, and the bot closes (ADR 044 D7)."""
    case = a_futures_wait_that_closes_on_exit(BELOW)
    case.price_is(D(100))
    assert case.world.state() is S.RUNNING

    case.price_is(D(99))
    assert case.world.state() is S.RUNNING, "the first beat after entry is not judged"

    case.price_is(D(99))
    assert case.world.state() is not S.RUNNING, "the second beat closes"


def test_a_mark_flickering_on_the_bound_after_entry_is_not_closed_on_the_first_beat() -> (
    None
):
    case = a_futures_wait_that_closes_on_exit(BELOW)
    case.price_is(D(100))

    case.price_is(D(99))
    case.price_is(D(100))
    case.price_is(D(101))

    assert case.world.state() is S.RUNNING
