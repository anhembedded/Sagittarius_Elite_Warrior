"""`BOT-189` — a fill a reconcile applies from history is announced once its runtime is kept.

A reconcile that ends in a mismatch throws its runtime away, so the next reconcile applies the same
fill again: announcing it the first time would tell the owner twice (review of PR #572).
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_order_filled_event import (
    BotOrderFilledEvent,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_reconciler import (
    filled_while_closed,
    restored,
)

S = BotLifecycleState


def _announced(world: GridWorld) -> list[BotOrderFilledEvent]:
    return [e for e in world.events.events if isinstance(e, BotOrderFilledEvent)]


def test_a_missed_fill_of_a_reconcile_that_halts_is_not_announced() -> None:
    world = restored()
    filled_while_closed(world, Decimal(110), "2.272")
    world.derive("1")  # the exchange's holding does not explain the fill: a mismatch
    world.hold("5")

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.INVENTORY_MISMATCH
    assert _announced(world) == []


def test_a_missed_fill_of_a_reconcile_that_is_kept_is_announced_once() -> None:
    world = restored()
    filled_while_closed(world, Decimal(110), "2.272")
    world.derive("2.272")
    world.hold("2.272")

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.RUNNING
    [event] = _announced(world)
    assert (event.side, event.price) == ("BUY", Decimal(110))
