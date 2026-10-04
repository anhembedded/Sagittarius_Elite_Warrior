"""`EPIC-029E` — a restored Grid reconciles with the exchange (ADR §3.3, D12).

A bot saved while RUNNING loads RECOVERING and places nothing; when trading is
enabled it claims its lease, re-registers, applies the fills it missed, adopts
the tagged orders it never saved, checks its inventory, and goes back to where
it was — or halts naming the disagreement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.client_order_id import (
    ClientOrderId,
    generate_client_order_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    SYMBOL,
    GridWorld,
    grid_world,
)

S = BotLifecycleState
_AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


def _restored(prior: BotLifecycleState = S.RUNNING) -> GridWorld:
    """A bot that ran its start, saved, and came back RECOVERING after a
    restart; its four ladder orders still rest on the exchange."""
    before = grid_world()
    before.executor.start()
    world = grid_world(
        state=S.RECOVERING, runtime=before.runtime(), recovering_from=prior
    )
    world.book.open = dict(before.book.open)
    world.derive("0")
    world.hold("0")
    return world


def _enable(world: GridWorld) -> None:
    world.executor.on_switch(True, TradingSwitchCause.ENABLED)


def _filled_while_closed(world: GridWorld, price: Decimal, quantity: str) -> None:
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


def _tagged(price: str, side: OrderSide = OrderSide.SELL) -> Order:
    return Order(
        ClientOrderId(generate_client_order_id(BOT)),
        SYMBOL,
        side,
        OrderType.LIMIT,
        Decimal(1),
        price=Decimal(price),
    )


def test_a_clean_restore_returns_to_running_and_places_nothing() -> None:
    world = _restored()

    _enable(world)

    assert world.state() is S.RUNNING
    assert world.book.requests == []


def test_a_restore_that_was_paused_returns_to_paused() -> None:
    world = _restored(prior=S.PAUSED)

    _enable(world)

    assert world.state() is S.PAUSED


def test_a_fill_missed_while_closed_is_applied_and_its_counter_placed() -> None:
    world = _restored()
    _filled_while_closed(world, Decimal(110), "2.272")
    world.derive("2.272")
    world.hold("2.272")

    _enable(world)

    assert world.state() is S.RUNNING
    assert [(r.side, r.reference_price) for r in world.book.requests] == [
        (OrderSide.SELL, Decimal(120))
    ]
    assert world.runtime().inventory == Decimal("2.272")


def test_an_order_sent_but_never_saved_is_adopted_and_its_level_not_placed_twice() -> (
    None
):
    """The crash before saving: the BUY at 110 filled and its counter SELL at
    120 was sent, then the app died before writing either."""
    world = _restored()
    _filled_while_closed(world, Decimal(110), "2.272")
    unsaved = _tagged("120")
    world.book.open[unsaved.client_order_id] = unsaved
    world.derive("2.272")
    world.hold("2.272")

    _enable(world)

    assert world.state() is S.RUNNING
    assert world.book.requests == []
    at_120 = [o for o in world.book.open.values() if o.price == Decimal(120)]
    assert at_120 == [unsaved]
    level = next(lv for lv in world.runtime().levels if lv.price == Decimal(120))
    assert level.order is not None
    assert level.order.client_order_id == unsaved.client_order_id


def test_a_saved_inventory_unlike_the_derived_one_halts() -> None:
    world = _restored()
    world.derive("1")
    world.hold("5")

    _enable(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.INVENTORY_MISMATCH


def test_a_user_holding_more_of_the_base_than_the_bot_is_not_halted() -> None:
    world = _restored()
    world.hold("7.5")

    _enable(world)

    assert world.state() is S.RUNNING


def test_an_account_holding_less_than_the_bot_bought_halts() -> None:
    world = _restored()
    _filled_while_closed(world, Decimal(110), "2.272")
    world.derive("2.272")
    world.hold("1")

    _enable(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.HOLDING_BELOW_INVENTORY


def test_two_tagged_orders_at_one_level_halt() -> None:
    world = _restored()
    extra = _tagged("100", OrderSide.BUY)
    world.book.open[extra.client_order_id] = extra

    _enable(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.DUPLICATE_LEVEL_ORDER


def test_a_tagged_order_at_no_level_halts() -> None:
    world = _restored()
    stray = _tagged("125")
    world.book.open[stray.client_order_id] = stray

    _enable(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.UNKNOWN_TAGGED_ORDER


def test_a_lease_held_by_another_owner_halts() -> None:
    world = _restored()
    world.session.claim_symbol(SYMBOL, "strategy")

    _enable(world)

    assert world.state() is S.HALTED
    assert world.runtime().reason is GridReason.LEASE_HELD


def test_a_refused_budget_leaves_the_bot_recovering() -> None:
    world = _restored()
    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(OwnerBudgetRefusal.INVENTORY_UNAVAILABLE)
    )

    _enable(world)

    assert world.state() is S.RECOVERING
    assert "inventory_unavailable" in world.runtime().reason_detail
    assert world.book.requests == []


def test_a_restored_bot_takes_its_lease_back_when_trading_is_enabled() -> None:
    world = grid_world(state=S.HALTED)

    _enable(world)

    assert not world.session.claim_symbol(SYMBOL, "manual")
    assert world.state() is S.HALTED


def test_a_stop_interrupted_by_a_restart_finishes_when_trading_is_enabled() -> None:
    before = grid_world()
    before.executor.start()
    world = grid_world(state=S.STOPPING, runtime=before.runtime())
    world.book.open = dict(before.book.open)

    world.executor.on_switch(False, TradingSwitchCause.DISABLED)
    assert world.state() is S.STOPPING
    _enable(world)

    assert world.state() is S.STOPPED
    assert world.book.open == {}
