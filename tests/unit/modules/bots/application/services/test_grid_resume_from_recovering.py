"""`BUG-204` — the executor's side of the owner's Resume out of RECOVERING.

@details A restart leaves the order session closed and a RECOVERING bot waits for
it to open. Resume is the desktop's way: `BotRunner.resume` opens the session
(`test_bot_runner_resume.py`), then the executor reconciles, booking an order that
filled meanwhile once, with its counter order, whether or not the session's own
switch-on event also reaches the bot.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_reconciler import (
    RESTORED_PAUSED_DETAIL,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)
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


class _HeldQueue(IBotWorkQueue):
    """Holds what is posted until `flush`: the order two callers' tasks reach a
    bot's one worker in, which the inline queue cannot show."""

    def __init__(self) -> None:
        self._tasks: list[Callable[[], None]] = []

    def post(self, task: Callable[[], None]) -> None:
        self._tasks.append(task)

    def close(self) -> None:
        return None

    def flush(self) -> None:
        while self._tasks:
            self._tasks.pop(0)()


def _recovering_with_held_queue(queue: _HeldQueue) -> GridWorld:
    before = grid_world()
    before.executor.start()
    world = grid_world(
        state=S.RECOVERING,
        runtime=before.runtime(),
        recovering_from=S.RUNNING,
        queue=queue,
    )
    world.book.open = dict(before.book.open)
    return world


def test_a_resume_queued_in_recovering_is_dropped_once_the_switch_reconcile_halted_the_bot() -> (
    None
):
    """The session's switch-on event reaches the worker before the Resume, and its
    reconcile halts the bot on a mismatch. The Resume was for leaving RECOVERING: it is
    dropped, not read as a HALTED bot's re-plan (no proposal, no budget, no cancel)."""
    queue = _HeldQueue()
    world = _recovering_with_held_queue(queue)
    world.derive("1")
    world.hold("5")

    world.executor.facts.on_switch(True, TradingSwitchCause.ENABLED)
    world.executor.resume()
    queue.flush()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.INVENTORY_MISMATCH
    assert world.executor.proposal is None
    assert world.book.requests == []


def test_a_bot_paused_before_the_restart_comes_back_paused_and_says_so() -> None:
    """`BUG-206`: the reconcile returns the owner's PAUSED bot to PAUSED and leaves a
    reason the screen shows; the next Resume runs it and clears that reason."""
    world = restored(S.PAUSED)

    world.executor.resume()

    assert world.state() is S.PAUSED
    assert world.runtime().reason is GridReason.RESTORED_PAUSED
    assert world.runtime().reason_detail == RESTORED_PAUSED_DETAIL

    world.executor.resume()

    assert world.state() is S.RUNNING
    assert world.runtime().reason is None
    assert world.runtime().reason_detail == ""


def test_a_bot_running_before_the_restart_carries_no_restored_paused_note() -> None:
    world = restored(S.RUNNING)

    world.executor.resume()

    assert world.state() is S.RUNNING
    assert world.runtime().reason is None
