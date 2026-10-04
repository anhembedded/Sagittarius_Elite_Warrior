"""`EPIC-029E` — a Grid's stop (ADR §3.1, §3.4, O3, D6).

The bot registers its budget again (re-deriving its inventory), cancels every
tagged order, keeps the base or sells it in slices under the cap, and is
STOPPED only when a read shows zero tagged orders — then it clears its budget
and gives back the lease. While trading is off it waits in STOPPING and
finishes when trading comes back. ERROR's exit is the same sequence.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.trading_switch_changed_event import (
    TradingSwitchCause,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_type import OrderType
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRegistrationResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.trading_limits import (
    TradingLimitViolation,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    BOT,
    CAP,
    LAST_PRICE,
    RUN_STARTED,
    SYMBOL,
    GridWorld,
    grid_world,
)

S = BotLifecycleState


def _running() -> GridWorld:
    world = grid_world()
    world.executor.start()
    world.book.requests.clear()
    return world


def _runtime(world: GridWorld) -> GridRuntime:
    return decode_runtime(world.store.load(BotId(BOT)).runtime)


def _derived(world: GridWorld, quantity: str) -> None:
    world.session.register_owner_budget_answers(
        OwnerBudgetRegistrationResult(
            None, OwnerInventory(Decimal(quantity), Decimal(0))
        )
    )


def test_stop_keeping_the_base_cancels_every_tagged_order_and_ends_stopped() -> None:
    world = _running()
    world.session.claim_symbol(SYMBOL, world.owner)
    ladder = set(world.book.open)

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPED
    assert set(world.book.cancels) == ladder
    assert world.book.open == {}
    assert [r for r in world.book.requests if r.order_type is OrderType.MARKET] == []
    assert world.owner not in world.session.budgets
    assert world.session.claim_symbol(SYMBOL, "manual")


def test_stop_registers_the_budget_again_before_any_cancel() -> None:
    """Trading clears every budget on a disable (ADR D6); the bot asks again,
    re-deriving its inventory, before it cancels or sells anything."""
    world = _running()
    world.session.budgets.clear()
    seen: list[bool] = []
    world.book.cancel_probe = lambda: seen.append(world.owner in world.session.budgets)

    world.executor.stop(BaseHandling.KEEP)

    assert seen
    assert all(seen)
    assert world.state() is S.STOPPED


def test_stop_selling_the_base_sells_the_derived_inventory_in_slices() -> None:
    """At the 300 cap and a price of 121 a slice is at most 2.479 BTC, so 4.9
    BTC goes as 2.479 then 2.421 (the ten-slice figure of the task is
    `test_market_slices.py`'s)."""
    world = _running()
    _derived(world, "4.9")

    world.executor.stop(BaseHandling.SELL_AT_MARKET)

    sells = [r for r in world.book.requests if r.order_type is OrderType.MARKET]
    assert [r.quantity for r in sells] == [Decimal("2.479"), Decimal("2.421")]
    assert all(
        r.side is OrderSide.SELL and r.quantity * LAST_PRICE <= CAP for r in sells
    )
    assert {r.client_order_tag for r in sells} == {BOT}
    assert world.state() is S.STOPPED


def test_a_refused_exit_slice_halts_naming_the_unsold_remainder() -> None:
    world = _running()
    _derived(world, "4.9")
    world.book.refuse_next = [
        None,
        TradingLimitViolation.OWNER_BUDGET_SELL_EXCEEDS_INVENTORY,
    ]

    world.executor.stop(BaseHandling.SELL_AT_MARKET)

    assert world.state() is S.HALTED
    runtime = _runtime(world)
    assert runtime.reason is GridReason.EXIT_SLICE_FAILED
    assert runtime.reason_detail.startswith("2.421 unsold after slice 2")


def test_stop_while_trading_is_off_waits_then_finishes_when_trading_returns() -> None:
    world = _running()
    world.executor.on_switch(False, TradingSwitchCause.DISABLED)
    world.session.set_enabled(enabled=False)

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPING
    assert "waiting" in _runtime(world).reason_detail
    assert world.book.cancels == []
    world.session.set_enabled(enabled=True)
    world.executor.on_switch(True, TradingSwitchCause.ENABLED)
    assert world.state() is S.STOPPED
    assert world.book.open == {}


def test_a_waiting_stop_keeps_the_users_choice_to_sell() -> None:
    world = _running()
    world.session.set_enabled(enabled=False)
    world.executor.stop(BaseHandling.SELL_AT_MARKET)
    assert _runtime(world).sell_base_on_stop

    world.session.set_enabled(enabled=True)
    _derived(world, "1")
    world.executor.on_switch(True, TradingSwitchCause.ENABLED)

    assert [
        r.side for r in world.book.requests if r.order_type is OrderType.MARKET
    ] == [OrderSide.SELL]
    assert world.state() is S.STOPPED


def test_stopped_only_when_no_tagged_order_is_left_open() -> None:
    world = _running()
    world.book.sticky = {next(iter(world.book.open))}

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPING
    assert "still open" in _runtime(world).reason_detail


def test_error_is_left_through_the_same_stop() -> None:
    world = grid_world(state=S.ERROR)
    world.session.budgets.clear()

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPED
    stored = world.store.load(BotId(BOT)).bot
    assert stored.lifecycle.run_started_at == RUN_STARTED


def test_a_stop_ignored_where_the_table_has_none() -> None:
    world = grid_world(state=S.STOPPED)

    world.executor.stop(BaseHandling.KEEP)

    assert world.state() is S.STOPPED
    assert world.book.cancels == []
