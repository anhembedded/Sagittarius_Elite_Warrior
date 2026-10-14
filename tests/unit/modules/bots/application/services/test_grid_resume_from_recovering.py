"""`BUG-204` — the executor's side of the owner's Resume out of RECOVERING.

@details A restart leaves the order session closed and a RECOVERING bot waits for
it to open. Resume is the desktop's way: `BotRunner.resume` opens the session
(`test_bot_runner_resume.py`), then the executor reconciles, booking an order that
filled meanwhile once, with its counter order, whether or not the session's own
switch-on event also reaches the bot.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_reconciler import (
    filled_while_closed,
    restored,
)

S = BotLifecycleState


def test_resume_books_the_fill_once_with_its_counter_order() -> None:
    world = restored()
    filled_while_closed(world, Decimal(110), "2.272")
    world.derive("2.272")
    world.hold("2.272")

    world.executor.resume()

    assert world.state() is S.RUNNING
    assert [(r.side, r.reference_price) for r in world.book.requests] == [
        (OrderSide.SELL, Decimal(120))
    ]
    assert world.runtime().inventory == Decimal("2.272")
    prices = [order.price for order in world.runtime().open_orders]
    assert len(prices) == len(set(prices))


def test_the_switch_on_event_after_a_resume_books_nothing_twice() -> None:
    """Opening the session publishes the switch-on event; it reaches a bot the
    Resume already reconciled and must change nothing."""
    world = restored()
    filled_while_closed(world, Decimal(110), "2.272")
    world.derive("2.272")
    world.hold("2.272")

    world.executor.resume()
    placed = list(world.book.requests)
    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.RUNNING
    assert world.book.requests == placed
    assert world.runtime().inventory == Decimal("2.272")
