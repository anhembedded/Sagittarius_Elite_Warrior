"""`EPIC-035J` (M1) — the price a Grid acts on has an age.

A tick is remembered with the moment it was heard. A use of the price that is
older than the limit reads the book instead, and remembers that reading with its
own moment. A resume proposal is priced at proposal time; the user's
confirmation prices it again, and a market that moved past the tolerance since
is refused with a named reason, never laid.

The clock is the fake monotonic one the test moves; nothing sleeps.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    GridWorld,
    grid_world,
    quote_at,
)

S = BotLifecycleState

_HEARD = Decimal(121)
_HOURS = 3 * 3600


def _running_with_a_tick() -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.executor.facts.on_tick(_HEARD)
    assert world.state() is S.RUNNING
    return world


def _halted_with_a_tick() -> GridWorld:
    world = _running_with_a_tick()
    world.executor.facts.on_switch(False, TradingSwitchCause.EMERGENCY_STOP)
    assert world.state() is S.HALTED
    world.derive("0")
    world.book.requests.clear()
    return world


def _book_reads(world: GridWorld) -> int:
    return world.entry_terms.book_reads.count(SYMBOL)


def _proposed_price(world: GridWorld) -> Decimal:
    proposal = world.executor.proposal
    assert proposal is not None
    return proposal.plan.last_price


def test_a_stale_price_is_refreshed_before_a_resume_proposal() -> None:
    world = _halted_with_a_tick()
    world.monotonic.advance(_HOURS)
    quote_at(world, Decimal(135))

    world.executor.resume()

    assert _proposed_price(world) == Decimal(135)


def test_a_fresh_tick_is_used_without_reading_the_book() -> None:
    world = _halted_with_a_tick()
    world.monotonic.advance(1)
    quote_at(world, Decimal(135))
    reads = _book_reads(world)

    world.executor.resume()

    assert _proposed_price(world) == _HEARD
    assert _book_reads(world) == reads


def test_the_refreshed_price_carries_its_own_age() -> None:
    """A price read from the book is as old as that read: the next use a moment
    later does not read the book again."""
    world = _halted_with_a_tick()
    world.monotonic.advance(_HOURS)
    quote_at(world, Decimal(135))
    reads = _book_reads(world)

    world.executor.resume()
    assert _book_reads(world) == reads + 1
    world.monotonic.advance(1)
    world.executor.resume()

    assert _book_reads(world) == reads + 1


def test_a_stop_sells_at_a_refreshed_price_not_an_hours_old_tick() -> None:
    world = _running_with_a_tick()
    world.derive("4.9")
    world.monotonic.advance(_HOURS)
    quote_at(world, Decimal(125))
    world.book.requests.clear()

    world.executor.stop(BaseHandling.SELL_AT_MARKET)

    sells = [r for r in world.book.requests if r.order_type is OrderType.MARKET]
    assert sells, "the stop must have sold the base at market"
    assert {r.reference_price for r in sells} == {Decimal(125)}


def test_a_proposal_that_moved_is_refused() -> None:
    world = _halted_with_a_tick()
    world.executor.resume()
    assert _proposed_price(world) == _HEARD
    quote_at(world, Decimal(140))

    world.executor.confirm_resume()

    assert world.state() is S.HALTED
    assert world.book.requests == [], "nothing is laid at a price the market left"
    assert world.executor.proposal is None
    runtime = world.runtime()
    assert runtime.reason is GridReason.PROPOSAL_PRICE_MOVED
    assert "121" in runtime.reason_detail
    assert "140" in runtime.reason_detail


def test_a_proposal_is_repriced_from_the_book_even_when_a_tick_is_fresh() -> None:
    """The confirmation may come hours after the proposal; the book, not the
    last tick, is what the ladder would sit against."""
    world = _halted_with_a_tick()
    world.executor.resume()
    world.executor.facts.on_tick(_HEARD)
    quote_at(world, Decimal(140))

    world.executor.confirm_resume()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.PROPOSAL_PRICE_MOVED


def test_a_proposal_inside_the_tolerance_is_laid() -> None:
    world = _halted_with_a_tick()
    world.executor.resume()
    quote_at(world, Decimal("121.5"))

    world.executor.confirm_resume()

    assert world.state() is S.RUNNING
    assert len(world.book.open) == 2, "no inventory: the buys only"


def test_after_a_refusal_resuming_again_proposes_at_the_new_price() -> None:
    world = _halted_with_a_tick()
    world.executor.resume()
    quote_at(world, Decimal(140))
    world.executor.confirm_resume()
    assert world.state() is S.HALTED

    world.monotonic.advance(_HOURS)
    world.executor.resume()
    assert _proposed_price(world) == Decimal(140)
    world.executor.confirm_resume()

    assert world.state() is S.RUNNING


def test_a_book_that_cannot_be_read_at_confirmation_refuses_rather_than_lays() -> None:
    world = _halted_with_a_tick()
    world.executor.resume()
    world.entry_terms.unquote(SYMBOL)

    world.executor.confirm_resume()

    assert world.state() is S.HALTED
    assert world.book.requests == []
    assert world.runtime().reason is GridReason.PROPOSAL_PRICE_MOVED
    assert "could not be read" in world.runtime().reason_detail
