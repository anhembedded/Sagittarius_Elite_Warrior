"""A running Grid whose user-data stream missed a fill (`EPIC-035B`).

`running()` is a bot that ran its start; `filled_in_the_gap()` is what the
exchange did while the stream was down: the order left the open orders and
history says it executed.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_work_queue import (
    IBotWorkQueue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    GridWorld,
    grid_world,
)

_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


class ManualWorkQueue(IBotWorkQueue):
    """A queue the test drains: tasks wait in the order posted, so a test can
    put an event *behind* a task that is about to run, as a real worker's
    queue does with a fill that arrives while a reconcile is reading."""

    def __init__(self) -> None:
        self._tasks: deque[Callable[[], None]] = deque()

    def post(self, task: Callable[[], None]) -> None:
        self._tasks.append(task)

    def close(self) -> None:
        return None

    def run_next(self) -> None:
        self._tasks.popleft()()

    def run_all(self) -> None:
        while self._tasks:
            self._tasks.popleft()()


def running() -> GridWorld:
    """A bot that ran its start: RUNNING, four ladder orders resting."""
    world = grid_world()
    world.executor.start()
    assert world.state() is BotLifecycleState.RUNNING
    world.derive(str(world.runtime().inventory))
    world.hold(str(world.runtime().inventory))
    return world


def filled_in_the_gap(world: GridWorld, price: Decimal, quantity: str) -> None:
    """The order at `price` filled while the stream was down: it left the open
    orders and history says it executed `quantity`."""
    order = world.book.open.pop(world.open_ids_by_price()[price])
    world.activity.orders.append(
        OrderRecord(
            order=Order(
                order.client_order_id,
                SYMBOL,
                order.side,
                OrderType.LIMIT,
                order.quantity,
                status=OrderStatus.FILLED,
                price=price,
            ),
            executed_quantity=Decimal(quantity),
            average_price=price,
            created_at=_AT,
            exchange_order_id=7,
        )
    )


def cancelled_in_the_gap(world: GridWorld, price: Decimal) -> None:
    """The order at `price` was cancelled on the exchange's website while the
    stream was down: it left the open orders and history shows it executed
    nothing."""
    order = world.book.open.pop(world.open_ids_by_price()[price])
    world.activity.orders.append(
        OrderRecord(
            order=Order(
                order.client_order_id,
                SYMBOL,
                order.side,
                OrderType.LIMIT,
                order.quantity,
                status=OrderStatus.CANCELED,
                price=price,
            ),
            executed_quantity=Decimal(0),
            average_price=None,
            created_at=_AT,
            exchange_order_id=8,
        )
    )


def partly_filled_in_the_gap(world: GridWorld, price: Decimal, quantity: str) -> None:
    """`quantity` of the order at `price` filled while the stream was down and
    the order stays open: history reports it PARTIALLY_FILLED."""
    order = world.book.open[world.open_ids_by_price()[price]]
    world.activity.orders.append(
        OrderRecord(
            order=Order(
                order.client_order_id,
                SYMBOL,
                order.side,
                OrderType.LIMIT,
                order.quantity,
                status=OrderStatus.PARTIALLY_FILLED,
                price=price,
            ),
            executed_quantity=Decimal(quantity),
            average_price=price,
            created_at=_AT,
            exchange_order_id=9,
        )
    )
