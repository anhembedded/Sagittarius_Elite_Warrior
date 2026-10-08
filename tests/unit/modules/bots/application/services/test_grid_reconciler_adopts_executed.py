"""`EPIC-035Q` (audit M10) — an adopted order keeps what it already executed.

An order the bot sent but never saved (the app died between the submit and the
write) is adopted by its tag at the level of its price. If it had already
partly filled, the exchange's open-order list carries no executed quantity, so
the adopted order started at zero: the saved inventory then disagreed with the
one derived from the exchange by exactly that part, and the bot halted at the
very reconcile that adopted it. History holds the executed quantity; the
reconcile reads it once for the saved orders already (`BUG-188`) and now reads
it for the adopted ones too.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    LevelOrder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_record import (
    OrderRecord,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.gap_world import (
    filled_in_the_gap,
    running,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    GridWorld,
)

S = BotLifecycleState
_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)
_BOUGHT = "2.272"


def _unsaved_sell_at_120(world: GridWorld, executed: str | None) -> str:
    """The counter SELL the bot sent for the BUY that filled in the gap and
    never saved. `executed` is what history says of it (`None`: history has no
    row for it yet). Returns its client order id."""
    resting = next(iter(world.book.open.values()))
    order_id = resting.client_order_id.replace(resting.client_order_id[-8:], "0badc0de")
    sell = Order(
        order_id,
        SYMBOL,
        OrderSide.SELL,
        OrderType.LIMIT,
        Decimal(_BOUGHT),
        price=Decimal(120),
    )
    world.book.open[order_id] = sell
    if executed is not None:
        world.activity.orders.append(
            OrderRecord(
                order=Order(
                    order_id,
                    SYMBOL,
                    OrderSide.SELL,
                    OrderType.LIMIT,
                    Decimal(_BOUGHT),
                    status=OrderStatus.PARTIALLY_FILLED,
                    price=Decimal(120),
                ),
                executed_quantity=Decimal(executed),
                average_price=Decimal(120),
                created_at=_AT,
                exchange_order_id=21,
            )
        )
    return order_id


def _adopted(world: GridWorld) -> LevelOrder:
    level = next(lv for lv in world.runtime().levels if lv.price == Decimal(120))
    assert level.order is not None
    return level.order


def _the_exchange_holds(world: GridWorld, derived: Decimal) -> None:
    world.derive(str(derived))
    world.hold(str(derived))


def test_an_adopted_partly_filled_order_keeps_its_executed_quantity() -> None:
    """Red before: the adopted SELL started at executed 0, the saved inventory
    stood 1.5 above the derived one and the bot halted INVENTORY_MISMATCH."""
    world = running()
    before = world.runtime().inventory
    filled_in_the_gap(world, Decimal(110), _BOUGHT)
    order_id = _unsaved_sell_at_120(world, executed="1.5")
    _the_exchange_holds(world, before + Decimal(_BOUGHT) - Decimal("1.5"))

    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert _adopted(world).client_order_id == order_id
    assert _adopted(world).executed == Decimal("1.5")
    assert world.runtime().inventory == before + Decimal(_BOUGHT) - Decimal("1.5")


def test_an_adopted_order_is_not_counted_again_by_the_next_reconcile() -> None:
    world = running()
    before = world.runtime().inventory
    filled_in_the_gap(world, Decimal(110), _BOUGHT)
    _unsaved_sell_at_120(world, executed="1.5")
    _the_exchange_holds(world, before + Decimal(_BOUGHT) - Decimal("1.5"))

    world.executor.facts.reconcile_after_gap()
    world.executor.facts.reconcile_after_gap()

    assert _adopted(world).executed == Decimal("1.5")
    assert world.state() is S.RUNNING


def test_an_adopted_order_that_executed_nothing_starts_at_zero() -> None:
    world = running()
    before = world.runtime().inventory
    filled_in_the_gap(world, Decimal(110), _BOUGHT)
    _unsaved_sell_at_120(world, executed="0")
    _the_exchange_holds(world, before + Decimal(_BOUGHT))

    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert _adopted(world).executed == 0


def test_an_adopted_order_history_does_not_list_yet_starts_at_zero() -> None:
    """History can lag the open-order list: no row is no evidence of a fill,
    and the next reconcile reads it again."""
    world = running()
    before = world.runtime().inventory
    filled_in_the_gap(world, Decimal(110), _BOUGHT)
    _unsaved_sell_at_120(world, executed=None)
    _the_exchange_holds(world, before + Decimal(_BOUGHT))

    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.RUNNING
    assert _adopted(world).executed == 0


def test_an_adopted_order_that_is_more_than_the_exchange_derives_still_halts() -> None:
    """The inventory check stays the judge: an adopted fill that the derived
    inventory does not show is a mismatch, not something to absorb."""
    world = running()
    before = world.runtime().inventory
    filled_in_the_gap(world, Decimal(110), _BOUGHT)
    _unsaved_sell_at_120(world, executed="1.5")
    _the_exchange_holds(world, before + Decimal(_BOUGHT))

    world.executor.facts.reconcile_after_gap()
    world.executor.facts.reconcile_after_gap()

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.INVENTORY_MISMATCH
