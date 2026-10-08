"""`EPIC-035V` (L9) — a Stop cancels a running Start between its steps.

A bot has one writer, so a Stop queued behind a Start waited for the whole of it:
every opening slice and every ladder order, each paced, only to cancel them. Now
`stop()` marks the request at once, the Start sees it before its next order and
gives up, and the queued Stop then cancels what was placed.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
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
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    GridWorld,
    grid_world,
)

S = BotLifecycleState

#: The opening buy's two slices and the ladder's four orders.
_FULL_START_ORDERS = 6


class SerialQueue(IBotWorkQueue):
    """One writer on the poster's thread: a task posted while another runs waits
    for it, as it does behind a real worker."""

    def __init__(self) -> None:
        self._pending: deque[Callable[[], None]] = deque()
        self._running = False

    def post(self, task: Callable[[], None]) -> None:
        self._pending.append(task)
        if self._running:
            return
        self._running = True
        try:
            while self._pending:
                self._pending.popleft()()
        finally:
            self._running = False

    def close(self) -> None:
        return None


def _stop_when_the_order_is_asked_for(world: GridWorld, turn: int) -> None:
    """The user presses Stop while the start waits its `turn`-th order's turn."""

    def wait_turn() -> None:
        world.pacer.turns += 1
        if world.pacer.turns == turn:
            world.executor.stop(BaseHandling.KEEP)

    world.pacer.wait_turn = wait_turn  # type: ignore[method-assign]


def test_a_stop_during_the_opening_buy_places_nothing_more_and_stops() -> None:
    world = grid_world(queue=SerialQueue())
    _stop_when_the_order_is_asked_for(world, turn=1)

    world.executor.start()

    assert len(world.book.requests) < _FULL_START_ORDERS
    assert world.book.open == {}
    assert world.state() is S.STOPPED
    assert world.runtime().reason is GridReason.USER_STOP


def test_a_stop_during_the_ladder_cancels_what_was_laid_and_lays_no_more() -> None:
    world = grid_world(queue=SerialQueue())
    _stop_when_the_order_is_asked_for(world, turn=4)

    world.executor.start()

    assert len(world.book.requests) < _FULL_START_ORDERS
    assert world.book.open == {}
    assert world.state() is S.STOPPED


def test_a_start_nobody_stopped_still_lays_the_whole_ladder() -> None:
    world = grid_world(queue=SerialQueue())

    world.executor.start()

    assert len(world.book.requests) == _FULL_START_ORDERS
    assert world.state() is S.RUNNING
