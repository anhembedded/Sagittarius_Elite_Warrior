"""`EPIC-029E` — a failure nobody named never leaves a bot stuck (ADR D9).

The gateway turns every order the exchange refuses or never answers into a
named outcome. Everything else the worker does can fail too: reading the book
for a price, reading the symbol's terms, reading order history. Such a failure
moves the bot to ERROR naming it, from which Stop runs, instead of being
swallowed by the queue with the bot left STARTING, STOPPING or RECOVERING and
no reason shown. A history read that fails during reconciliation is a wait,
not a fault: the bot stays RECOVERING and the next enable retries.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_price_tick import (
    PriceTick,
)
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    grid_world,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.test_grid_reconciler import (
    filled_while_closed,
    restored,
)

S = BotLifecycleState


def test_a_start_that_cannot_read_a_price_is_an_error_naming_it() -> None:
    world = grid_world(book_readable=False)

    world.executor.start()

    assert world.state() is S.ERROR
    runtime = world.runtime()
    assert runtime.reason is GridReason.TASK_FAILED
    assert runtime.reason_detail.startswith("start: ")
    assert world.book.requests == []


def test_a_stop_that_cannot_read_a_price_is_an_error_and_stop_runs_again() -> None:
    world = grid_world(state=S.RUNNING, book_readable=False)

    world.executor.stop(BaseHandling.SELL_AT_MARKET)

    assert world.state() is S.ERROR
    assert world.runtime().reason is GridReason.TASK_FAILED
    world.executor.facts.on_tick(PriceTick.at(Decimal(121)))
    world.executor.stop(BaseHandling.KEEP)
    assert world.state() is S.STOPPED


def test_history_unavailable_while_reconciling_waits_in_recovering() -> None:
    world = restored()
    filled_while_closed(world, Decimal(110), "2.272")
    world.derive("2.272")
    world.hold("2.272")
    world.activity.history_unavailable = True

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.RECOVERING
    assert world.runtime().reason is GridReason.HISTORY_UNAVAILABLE
    assert "waiting" in world.runtime().reason_detail
    assert world.book.requests == []

    world.activity.history_unavailable = False
    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)

    assert world.state() is S.RUNNING
