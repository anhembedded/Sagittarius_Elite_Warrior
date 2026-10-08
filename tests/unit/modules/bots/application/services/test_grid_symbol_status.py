"""`EPIC-035E` (M5) — a symbol that does not trade pauses or halts the bot, by name, never ERROR.

The status was parsed and nothing read it: the bot kept submitting, the exchange
refused every order, and the first refusal that raised ended in ERROR. Now the
status gates Start and Resume, and an exchange refusal for the status is a named
PAUSE (the orders it could not place are held for the resume) or, for a symbol
the exchange no longer lists, a named HALT that takes the ladder off.
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_rejection_reason import (
    OrderRejectedByExchangeError,
    OrderRejectionReason,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_MARKET_CLOSED = "-1013 Market is closed."


def _refused_for(reason: OrderRejectionReason) -> OrderRejectedByExchangeError:
    return OrderRejectedByExchangeError(reason, _MARKET_CLOSED)


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    assert world.state() is S.RUNNING
    return world


def _paused_for_the_status() -> GridWorld:
    """RUNNING, and the counter order of a fill at 110 refused for the status."""
    world = _running()
    world.book.raise_next = [_refused_for(OrderRejectionReason.SYMBOL_NOT_TRADING)]
    world.fill(Decimal(110), "2.272")
    return world


def test_a_symbol_in_break_pauses_the_bot_with_a_named_reason() -> None:
    world = _paused_for_the_status()

    assert world.state() is S.PAUSED, "a refusal for the status is not a fault"
    runtime = world.runtime()
    assert runtime.reason is GridReason.SYMBOL_NOT_TRADING
    assert "Market is closed" in runtime.reason_detail
    assert len(runtime.held) == 1, "the counter order it could not place is kept"
    assert world.book.open, "a pause leaves the ladder resting"
    assert world.book.cancels == []


def test_a_bot_paused_for_the_status_does_not_resume_while_it_persists() -> None:
    world = _paused_for_the_status()
    sent = list(world.book.submitted)
    world.set_status("BREAK")

    world.executor.resume()

    assert world.state() is S.PAUSED
    assert world.runtime().reason is GridReason.SYMBOL_NOT_TRADING
    assert "BREAK" in world.runtime().reason_detail, "the status is on the bot"
    assert world.book.submitted == sent, "nothing was sent while it does not trade"
    assert len(world.runtime().held) == 1


def test_a_bot_paused_for_the_status_resumes_once_it_trades_and_places_what_it_held() -> (
    None
):
    world = _paused_for_the_status()
    world.set_status("BREAK")
    world.executor.resume()
    world.set_status("TRADING")

    world.executor.resume()

    assert world.state() is S.RUNNING
    assert world.runtime().held == ()
    assert Decimal(120) in world.open_ids_by_price(), "the held counter order rests"


def test_a_refusal_for_the_status_while_resuming_pauses_again_and_keeps_the_orders() -> (
    None
):
    world = _paused_for_the_status()
    world.book.raise_next = [_refused_for(OrderRejectionReason.SYMBOL_NOT_TRADING)]

    world.executor.resume()

    assert world.state() is S.PAUSED
    assert len(world.runtime().held) == 1, "the held order is held again, not lost"


def test_a_symbol_that_does_not_trade_refuses_the_start_before_any_order() -> None:
    world = grid_world()
    world.set_status("BREAK")

    world.executor.start()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SYMBOL_NOT_TRADING
    assert "BREAK" in world.runtime().reason_detail
    assert world.book.requests == [], "no order was attempted"


def test_cancel_only_still_allows_stop() -> None:
    """Lock: the gate guards placing; a stop only cancels, and CANCEL_ONLY allows that."""
    world = _paused_for_the_status()
    world.set_status("CANCEL_ONLY")
    world.derive("0")
    world.hold("0")

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPED
    assert world.book.open == {}


def test_a_delisting_halts_the_bot() -> None:
    """The exchange no longer lists the symbol: a start is refused by name, and an
    order refused for it halts the bot and takes the ladder off."""
    refused_start = grid_world()
    refused_start.terms.unlist(refused_start.executor.symbol)
    refused_start.executor.start()

    assert refused_start.state() is S.HALTED
    assert refused_start.runtime().reason is GridReason.SYMBOL_DELISTED
    assert refused_start.book.requests == []

    running = _running()
    running.book.raise_next = [_refused_for(OrderRejectionReason.SYMBOL_NOT_LISTED)]
    running.fill(Decimal(110), "2.272")

    assert running.state() is S.HALTED
    assert running.runtime().reason is GridReason.SYMBOL_DELISTED
    assert running.book.open == {}, "a halt takes the ladder off"


def test_a_refusal_for_the_status_while_starting_halts_by_name() -> None:
    world = grid_world()
    world.book.raise_next = [_refused_for(OrderRejectionReason.SYMBOL_NOT_TRADING)]

    world.executor.start()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.SYMBOL_NOT_TRADING


def test_any_other_refusal_that_raised_is_still_a_fault() -> None:
    world = _running()
    world.book.raise_next = [_refused_for(OrderRejectionReason.PRICE_FILTER)]

    world.fill(Decimal(110), "2.272")

    assert world.state() is S.ERROR
