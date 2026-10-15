"""`EPIC-039I` - a SHORT grid's books: its entries are SELLs, its completions BUYs.

@details The same reactions that book a long grid (`grid_reactions.on_fill`) book a short one when
the runtime's `entry_side` is SELL: a SELL deepens the negative inventory at its proceeds, a BUY
covers it and books `(average entry - price)`, a completed cycle's profit is `entry - completion`.
A Spot or LONG runtime is booked as it always was; those figures are the Spot oracle's.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_books import (
    book_market_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LevelFill,
    PlaceOrder,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    STEP,
    empty_ladder,
    order_id,
    perform,
    resting,
)

D = Decimal


def _short_ladder() -> GridRuntime:
    """Levels 100..140; opening: a market SELL of 2 at 121; BUYs rest at L0 and L1 (they
    reduce the opening), SELLs at L3 and L4 (entries)."""
    runtime = replace(empty_ladder(), entry_side=OrderSide.SELL)
    runtime = book_market_fill(runtime, OrderSide.SELL, LevelFill("open", D(121), D(2)))
    runtime = resting(runtime, 0, OrderSide.BUY)
    runtime = resting(runtime, 1, OrderSide.BUY)
    runtime = resting(runtime, 3, OrderSide.SELL)
    return resting(runtime, 4, OrderSide.SELL)


def test_the_opening_sell_is_a_short_position_at_its_proceeds() -> None:
    runtime = _short_ladder()

    assert runtime.inventory == -2
    assert runtime.cost == 242
    assert runtime.average_cost == 121


def test_a_filled_sell_entry_owes_a_paired_buy_one_level_down() -> None:
    reaction = on_fill(
        _short_ladder(), LevelFill(order_id(3), D(130), D(1)), STEP, hold=False
    )

    (counter,) = reaction.actions
    assert isinstance(counter, PlaceOrder)
    assert (counter.level_index, counter.side, counter.price) == (
        2,
        OrderSide.BUY,
        D(120),
    )
    assert counter.quantity == 1
    assert counter.paired_buy_price == D(130), "the entry the completion closes"
    assert reaction.runtime.inventory == -3
    assert reaction.runtime.completed_cycles == 0


def test_the_completing_buy_books_the_cycle_profit_and_covers_the_short() -> None:
    entered = on_fill(
        _short_ladder(), LevelFill(order_id(3), D(130), D(1)), STEP, hold=False
    )
    (completion,) = entered.actions
    assert isinstance(completion, PlaceOrder)
    runtime = perform(entered.runtime, completion)

    done = on_fill(runtime, LevelFill(order_id(2), D(120), D(1)), STEP, hold=False)

    after = done.runtime
    assert after.completed_cycles == 1
    assert after.realised_profit == 10, "sold at 130, bought back at 120"
    assert after.inventory == -2
    # The average entry was (242 + 130) / 3 = 124; covering one at 120 earns 4 of it.
    assert after.realised_total == 4
    assert after.cost == 248
    (next_entry,) = done.actions
    assert isinstance(next_entry, PlaceOrder)
    assert (next_entry.side, next_entry.level_index) == (OrderSide.SELL, 3)
    assert next_entry.paired_buy_price is None, "a fresh entry pairs nothing"


def test_a_buy_of_the_opening_covers_it_and_pairs_no_cycle() -> None:
    reaction = on_fill(
        _short_ladder(), LevelFill(order_id(1), D(110), D(1)), STEP, hold=False
    )

    assert reaction.runtime.inventory == -1
    assert reaction.runtime.completed_cycles == 0
    assert reaction.runtime.realised_total == 11, "sold at 121, bought back at 110"
    (entry,) = reaction.actions
    assert isinstance(entry, PlaceOrder)
    assert (entry.side, entry.level_index) == (OrderSide.SELL, 2)


def test_a_long_runtime_is_booked_as_it_always_was() -> None:
    runtime = book_market_fill(
        empty_ladder(), OrderSide.BUY, LevelFill("o", D(121), D(2))
    )
    runtime = resting(runtime, 3, OrderSide.SELL)

    reaction = on_fill(runtime, LevelFill(order_id(3), D(130), D(1)), STEP, hold=False)

    assert reaction.runtime.inventory == 1
    assert reaction.runtime.realised_total == 9


def test_a_neutral_book_crosses_zero_booking_what_it_covers_and_opening_the_rest() -> (
    None
):
    """A fill larger than the position (a part fill whose rest ended left it off a whole
    quantity) covers what is held and opens the other side with the remainder."""
    neutral = replace(empty_ladder(), entry_side=None)
    neutral = book_market_fill(neutral, OrderSide.BUY, LevelFill("a", D(100), D("0.7")))

    crossed = book_market_fill(neutral, OrderSide.SELL, LevelFill("b", D(110), D(1)))

    assert crossed.inventory == D("-0.3")
    assert crossed.realised_total == D("7.0"), "0.7 covered at +10"
    assert crossed.average_cost == 110, "the short that is left was opened at 110"
    assert crossed.cost == D("33.0")


def _neutral_ladder() -> GridRuntime:
    """Levels 100..140, no opening; entries rest on both sides: BUYs at L0 and L1, SELLs at L3
    and L4. Either side may open a cycle."""
    runtime = replace(empty_ladder(), entry_side=None)
    runtime = resting(runtime, 0, OrderSide.BUY)
    runtime = resting(runtime, 1, OrderSide.BUY)
    runtime = resting(runtime, 3, OrderSide.SELL)
    return resting(runtime, 4, OrderSide.SELL)


def test_a_neutral_sell_entry_owes_a_paired_buy_and_a_buy_entry_a_paired_sell() -> None:
    sold = on_fill(
        _neutral_ladder(), LevelFill(order_id(3), D(130), D(1)), STEP, hold=False
    )
    bought = on_fill(
        _neutral_ladder(), LevelFill(order_id(1), D(110), D(1)), STEP, hold=False
    )

    (buy_back,) = sold.actions
    (sell_back,) = bought.actions
    assert isinstance(buy_back, PlaceOrder) and isinstance(sell_back, PlaceOrder)
    assert (buy_back.side, buy_back.level_index, buy_back.paired_buy_price) == (
        OrderSide.BUY,
        2,
        D(130),
    )
    assert (sell_back.side, sell_back.level_index, sell_back.paired_buy_price) == (
        OrderSide.SELL,
        2,
        D(110),
    )


def test_a_neutral_completion_books_the_cycle_whichever_side_it_is_and_owes_an_unpaired_entry() -> (
    None
):
    sold = on_fill(
        _neutral_ladder(), LevelFill(order_id(3), D(130), D(1)), STEP, hold=False
    )
    (buy_back,) = sold.actions
    assert isinstance(buy_back, PlaceOrder)
    done = on_fill(
        perform(sold.runtime, buy_back),
        LevelFill(order_id(2), D(120), D(1)),
        STEP,
        hold=False,
    )

    assert done.runtime.completed_cycles == 1
    assert done.runtime.realised_profit == 10, "sold at 130, bought back at 120"
    assert done.runtime.inventory == 0
    (entry,) = done.actions
    assert isinstance(entry, PlaceOrder)
    assert (entry.side, entry.level_index, entry.paired_buy_price) == (
        OrderSide.SELL,
        3,
        None,
    )
