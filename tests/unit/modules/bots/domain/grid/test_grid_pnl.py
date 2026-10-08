"""`EPIC-035M` (L2) — the total is realised plus unrealised, and a sell of the opening base counts.

Grid profit books only completed buy/sell cycles, so the sell of the opening
inventory (a stop, an exit slice) moved no profit and the screen's "grid profit"
and the account's gain disagreed. `realised_total` books every sell against the
average cost, `pnl_summary` adds the unrealised on the bot's own price, and the
HODL benchmark is what the same capital would be worth held since the start.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_pnl import (
    pnl_summary,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LevelFill,
    book_market_fill,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    PRICES,
    STEP,
    order_id,
    started_ladder,
)


def _held(inventory: str, cost: str) -> GridRuntime:
    base = started_ladder()
    return GridRuntime(base.levels, inventory=Decimal(inventory), cost=Decimal(cost))


def test_selling_the_opening_base_books_realised_pnl_against_the_average_cost() -> None:
    """2 held for 230 (average 115); 1 sold at 130 paying 0.13 quote: 130 − 115 − 0.13."""
    fill = LevelFill(order_id(3), PRICES[3], Decimal(1), quote_fee=Decimal("0.13"))

    sold = on_fill(_held("2", "230"), fill, STEP, hold=False).runtime

    assert sold.realised_total == Decimal("14.87")
    assert sold.realised_profit == 0, "a grid cycle was not completed"


def test_an_exit_slice_books_realised_pnl_too() -> None:
    fill = LevelFill("SEW-a3f9c1-market", Decimal(120), Decimal(2))

    sold = book_market_fill(_held("2", "230"), OrderSide.SELL, fill)

    assert sold.realised_total == Decimal(10)
    assert sold.inventory == 0


def test_a_buy_books_no_realised_pnl() -> None:
    fill = LevelFill(order_id(1), PRICES[1], Decimal(1))

    bought = on_fill(started_ladder(), fill, STEP, hold=False).runtime

    assert bought.realised_total == 0


def test_total_pnl_is_realised_plus_unrealised_on_the_bots_own_price() -> None:
    runtime = GridRuntime(
        started_ladder().levels,
        inventory=Decimal(2),
        cost=Decimal(230),
        realised_total=Decimal(15),
        realised_profit=Decimal(9),
        mark_price=Decimal(125),
    )

    summary = pnl_summary(runtime, capital=Decimal(1000))

    assert summary.unrealised == Decimal(20)
    assert summary.realised == Decimal(15)
    assert summary.total == Decimal(35)
    assert summary.grid_profit == Decimal(9)


def test_without_a_price_there_is_no_unrealised_and_no_total() -> None:
    runtime = GridRuntime(
        started_ladder().levels, inventory=Decimal(2), cost=Decimal(230)
    )

    summary = pnl_summary(runtime, capital=Decimal(1000))

    assert summary.unrealised is None
    assert summary.total is None


def test_a_flat_bot_has_a_total_equal_to_its_realised() -> None:
    runtime = GridRuntime(
        started_ladder().levels, realised_total=Decimal(7), mark_price=Decimal(125)
    )

    summary = pnl_summary(runtime, capital=Decimal(1000))

    assert summary.unrealised == 0
    assert summary.total == Decimal(7)


def test_the_hodl_benchmark_is_the_capital_held_from_the_start_price() -> None:
    """1000 at 100 buys 10; at 125 they are worth 1250: a gain of 250."""
    runtime = GridRuntime(
        started_ladder().levels, start_price=Decimal(100), mark_price=Decimal(125)
    )

    assert pnl_summary(runtime, capital=Decimal(1000)).hodl == Decimal(250)


def test_hodl_needs_a_start_price_and_a_current_one() -> None:
    no_start = GridRuntime(started_ladder().levels, mark_price=Decimal(125))
    no_mark = GridRuntime(started_ladder().levels, start_price=Decimal(100))

    assert pnl_summary(no_start, capital=Decimal(1000)).hodl is None
    assert pnl_summary(no_mark, capital=Decimal(1000)).hodl is None


def test_unpriced_fees_are_carried_so_the_screen_can_say_the_total_is_incomplete() -> (
    None
):
    runtime = GridRuntime(started_ladder().levels, unpriced_fees=2)

    assert pnl_summary(runtime, capital=Decimal(1000)).unpriced_fees == 2
