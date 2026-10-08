"""`EPIC-029E` — from a plan to a live ladder (ADR §3.1, §3.4, D11, D13).

The report's example plan (65,000 in 60,000–70,000, 10 grids) is the subject:
the start places outward from the price and leaves the nearest level empty; a
resume sizes the SELL side to the inventory and buys nothing; a price at an exit
names it.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_evaluation import (
    evaluate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    buys_within_capital,
    crossed_exit,
    ladder_orders,
    resized_for_inventory,
    runtime_from_plan,
    sells_net_of_opening_fee,
    unplaced_inventory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    GridPlan,
    LevelSide,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LadderRules,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    GridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
    inputs,
)


def _report_plan() -> GridPlan:
    evaluation = evaluate_grid(inputs(), GridThresholds())
    assert evaluation.plan is not None
    return evaluation.plan


def test_the_ladder_goes_out_from_the_price_and_the_nearest_level_stays_empty() -> None:
    plan = _report_plan()

    orders = ladder_orders(plan)

    distances = [abs(order.price - plan.last_price) for order in orders]
    assert distances == sorted(distances)
    empty = next(level for level in plan.levels if level.side is LevelSide.EMPTY)
    assert empty.index not in {order.level_index for order in orders}
    assert {order.level_index for order in orders} == {
        level.index for level in plan.order_levels
    }


def test_each_order_keeps_its_levels_side_price_and_quantity() -> None:
    plan = _report_plan()

    by_level = {order.level_index: order for order in ladder_orders(plan)}

    for level in plan.order_levels:
        order = by_level[level.index]
        expected = OrderSide.SELL if level.side is LevelSide.SELL else OrderSide.BUY
        assert (order.side, order.price, order.quantity) == (
            expected,
            level.price,
            level.quantity,
        )


def test_a_fresh_runtime_is_all_empty_with_each_levels_buy_quantity() -> None:
    plan = _report_plan()

    runtime = runtime_from_plan(plan, TERMS.step_size)

    assert all(level.state is LevelState.EMPTY for level in runtime.levels)
    for level, planned in zip(runtime.levels, plan.levels, strict=True):
        assert level.price == planned.price
        assert level.buy_quantity * planned.price <= plan.capital_per_level
        assert (level.buy_quantity + TERMS.step_size) * planned.price > (
            plan.capital_per_level
        )


def test_a_resume_sizes_the_sell_side_to_the_inventory_nearest_first() -> None:
    plan = _report_plan()
    sells = sorted(plan.sell_levels, key=lambda level: level.price)
    inventory = sells[0].quantity + sells[1].quantity / 2

    resized = resized_for_inventory(plan, inventory, TERMS.min_notional)

    by_index = {level.index: level for level in resized.levels}
    assert by_index[sells[0].index].quantity == sells[0].quantity
    assert by_index[sells[1].index].quantity == sells[1].quantity / 2
    for far in sells[2:]:
        assert by_index[far.index].side is LevelSide.EMPTY
        assert by_index[far.index].quantity == 0
    assert resized.opening_buy_quantity == 0
    assert resized.buy_levels == plan.buy_levels


def test_a_resume_leaves_empty_a_sell_level_worth_less_than_the_minimum() -> None:
    """What the inventory leaves for the next SELL level is worth under the
    exchange's NOTIONAL minimum: Binance would refuse it, so that level stays
    EMPTY and the remainder is dust in the inventory."""
    plan = _report_plan()
    sells = sorted(plan.sell_levels, key=lambda level: level.price)
    dust = (TERMS.min_notional / sells[1].price / 2).quantize(TERMS.step_size)
    inventory = sells[0].quantity + dust

    resized = resized_for_inventory(plan, inventory, TERMS.min_notional)

    by_index = {level.index: level for level in resized.levels}
    assert by_index[sells[0].index].quantity == sells[0].quantity
    assert by_index[sells[1].index].side is LevelSide.EMPTY
    assert by_index[sells[1].index].quantity == 0


def test_a_resume_with_no_inventory_keeps_only_the_buy_side() -> None:
    resized = resized_for_inventory(_report_plan(), Decimal(0), TERMS.min_notional)

    assert resized.sell_levels == ()
    assert ladder_orders(resized) and all(
        order.side is OrderSide.BUY for order in ladder_orders(resized)
    )


def test_an_exit_is_crossed_at_its_price_and_beyond() -> None:
    stop, take = Decimal(57000), Decimal(73500)

    assert crossed_exit(Decimal(57000), stop, take) is GridReason.STOP_LOSS
    assert crossed_exit(Decimal("56999.99"), stop, take) is GridReason.STOP_LOSS
    assert crossed_exit(Decimal("57000.01"), stop, take) is None
    assert crossed_exit(Decimal(73500), stop, take) is GridReason.TAKE_PROFIT
    assert crossed_exit(Decimal("73499.99"), stop, take) is None
    assert crossed_exit(Decimal(1), None, None) is None


def test_the_sell_side_is_sized_to_what_the_opening_receives_net_of_its_fee() -> None:
    """On Spot a buy's fee is taken from the base it buys: the opening receives
    `quantity × (1 − taker)`, so a SELL side sized to the planned quantity
    would ask trading to sell more than the bot holds (check 3) on its last
    level. Each SELL is shrunk by the fee and rounded down to the step."""
    plan = _report_plan()

    netted = sells_net_of_opening_fee(plan, TERMS.taker_fee, TERMS.step_size)

    received = plan.opening_buy_quantity * (1 - TERMS.taker_fee)
    assert sum(level.quantity for level in netted.sell_levels) <= received
    for before, after in zip(plan.sell_levels, netted.sell_levels, strict=True):
        assert after.quantity <= before.quantity * (1 - TERMS.taker_fee)
        assert after.quantity + TERMS.step_size > before.quantity * (
            1 - TERMS.taker_fee
        )
    assert netted.buy_levels == plan.buy_levels
    assert netted.opening_buy_quantity == plan.opening_buy_quantity


def test_the_buy_side_shares_only_the_capital_the_inventory_leaves() -> None:
    plan = _report_plan()
    buys = plan.buy_levels
    left = plan.capital_per_level * len(buys) / 2

    shrunk = buys_within_capital(
        plan, left, LadderRules(TERMS.step_size, TERMS.min_notional)
    )

    assert sum((lv.price * lv.quantity for lv in shrunk.buy_levels), Decimal(0)) <= left
    assert len(shrunk.buy_levels) == len(buys)
    assert shrunk.sell_levels == plan.sell_levels


def test_a_buy_side_with_more_left_than_planned_keeps_its_planned_size() -> None:
    plan = _report_plan()

    kept = buys_within_capital(
        plan,
        plan.capital_per_level * 100,
        LadderRules(TERMS.step_size, TERMS.min_notional),
    )

    assert kept.buy_levels == plan.buy_levels


def test_a_buy_level_whose_share_is_under_the_minimum_stays_empty() -> None:
    plan = _report_plan()

    shrunk = buys_within_capital(
        plan, TERMS.min_notional, LadderRules(TERMS.step_size, TERMS.min_notional)
    )

    assert shrunk.buy_levels == ()
    assert len(shrunk.levels) == len(plan.levels)


def test_nothing_left_leaves_no_buy_level() -> None:
    plan = _report_plan()

    shrunk = buys_within_capital(
        plan, Decimal(-5), LadderRules(TERMS.step_size, TERMS.min_notional)
    )

    assert shrunk.buy_levels == ()


def test_the_inventory_the_sell_levels_do_not_reach_is_counted() -> None:
    plan = _report_plan()
    sold = sum((lv.quantity for lv in plan.sell_levels), Decimal(0))

    assert unplaced_inventory(plan, sold + Decimal("0.5")) == Decimal("0.5")
    assert unplaced_inventory(plan, sold) == 0
    assert unplaced_inventory(plan, sold / 2) == 0
