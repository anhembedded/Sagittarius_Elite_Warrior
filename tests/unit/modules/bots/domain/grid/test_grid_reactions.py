"""`EPIC-029E` — the business promises of a Grid's reactions (ADR D10, §3.2).

A fill accumulates per order; only the full fill emits a counter order, one
level away; a completed cycle books its profit once; an order that ends is
re-placed once, and a second end within a minute or a rejection halts; a pause
holds counter orders and resume releases them.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    Halt,
    LevelFill,
    PlaceOrder,
    on_end,
    on_fill,
    place_failed,
    release_held,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.grid_runtime_builders import (
    PRICES,
    STEP,
    empty_ladder,
    order_id,
    perform,
    started_ladder,
)

AT = datetime(2026, 10, 4, 9, tzinfo=UTC)


def _fill(
    index: int, quantity: str, base_fee: str = "0", quote_fee: str = "0"
) -> LevelFill:
    return LevelFill(
        order_id(index),
        PRICES[index],
        Decimal(quantity),
        Decimal(base_fee),
        Decimal(quote_fee),
    )


def _only_order(actions: tuple[PlaceOrder | Halt, ...]) -> PlaceOrder:
    assert len(actions) == 1
    action = actions[0]
    assert isinstance(action, PlaceOrder)
    return action


def test_a_partial_fill_accumulates_and_places_nothing() -> None:
    reaction = on_fill(started_ladder(), _fill(1, "0.4"), STEP, hold=False)

    level = reaction.runtime.levels[1]
    assert level.state is LevelState.PARTIAL
    assert level.order is not None
    assert level.order.executed == Decimal("0.4")
    assert reaction.actions == ()
    assert reaction.runtime.inventory == Decimal("0.4")


def test_a_full_buy_places_one_sell_one_level_up_net_of_the_base_fee() -> None:
    reaction = on_fill(
        started_ladder(), _fill(1, "1", base_fee="0.001"), STEP, hold=False
    )

    assert reaction.actions == (
        PlaceOrder(
            2, OrderSide.SELL, PRICES[2], Decimal("0.999"), PRICES[1], Decimal("0.110")
        ),
    )
    assert reaction.runtime.levels[1].state is LevelState.EMPTY
    assert reaction.runtime.levels[1].order is None
    assert reaction.runtime.inventory == Decimal("0.999")


def test_three_partial_events_make_exactly_one_counter_order() -> None:
    runtime = started_ladder()
    counters: list[PlaceOrder | Halt] = []
    for piece in ("0.3", "0.3", "0.4"):
        reaction = on_fill(runtime, _fill(1, piece), STEP, hold=False)
        runtime = reaction.runtime
        counters.extend(reaction.actions)

    assert counters == [PlaceOrder(2, OrderSide.SELL, PRICES[2], Decimal(1), PRICES[1])]


def test_a_late_duplicate_fill_after_the_level_settled_changes_nothing() -> None:
    settled = on_fill(started_ladder(), _fill(1, "1"), STEP, hold=False).runtime

    again = on_fill(settled, _fill(1, "1"), STEP, hold=False)

    assert again.runtime == settled
    assert again.actions == ()


def test_a_full_sell_places_the_level_below_its_buy_quantity() -> None:
    reaction = on_fill(started_ladder(), _fill(3, "1"), STEP, hold=False)

    assert reaction.actions == (PlaceOrder(2, OrderSide.BUY, PRICES[2], Decimal(1)),)


def test_a_completed_cycle_books_its_profit_once_with_both_legs_fees() -> None:
    """Buy 1 at 110 paying 0.001 base, sell the 0.999 one level up at 120
    paying 0.11988 quote: (120 − 110) × 0.999 − 0.11988 − 0.110 = 9.76012."""
    bought = on_fill(
        started_ladder(), _fill(1, "1", base_fee="0.001"), STEP, hold=False
    )
    with_sell = perform(bought.runtime, _only_order(bought.actions))

    sold = on_fill(with_sell, _fill(2, "0.999", quote_fee="0.11988"), STEP, hold=False)

    assert sold.runtime.realised_profit == Decimal("9.76012")
    assert sold.runtime.completed_cycles == 1
    again = on_fill(sold.runtime, _fill(2, "0.999"), STEP, hold=False)
    assert again.runtime.realised_profit == Decimal("9.76012")


def test_a_cycle_matches_the_planners_per_grid_profit_to_within_the_sell_fee_rate() -> (
    None
):
    """`grid_derived` charges both legs the maker rate on the buy price; a real
    sell pays it on the sell price. The two differ by maker × (sell − buy) ×
    quantity, and by nothing else."""
    maker = Decimal("0.001")
    bought = on_fill(
        started_ladder(),
        _fill(1, "1", quote_fee=str(maker * PRICES[1])),
        STEP,
        hold=False,
    )
    with_sell = perform(bought.runtime, _only_order(bought.actions))
    sold = on_fill(
        with_sell, _fill(2, "1", quote_fee=str(maker * PRICES[2])), STEP, hold=False
    )

    planner = ((PRICES[2] - PRICES[1]) / PRICES[1] - 2 * maker) * PRICES[1]
    assert sold.runtime.realised_profit - planner == -maker * (PRICES[2] - PRICES[1])


def test_selling_opening_bought_base_moves_the_inventory_and_books_no_grid_profit() -> (
    None
):
    runtime = started_ladder()
    runtime = GridRuntime(runtime.levels, inventory=Decimal(2), cost=Decimal(230))

    sold = on_fill(runtime, _fill(3, "1"), STEP, hold=False)

    assert sold.runtime.realised_profit == 0
    assert sold.runtime.completed_cycles == 0
    assert sold.runtime.inventory == Decimal(1)
    assert sold.runtime.cost == Decimal(115)


def test_an_ended_order_is_re_placed_once_for_what_it_still_owes() -> None:
    partly = on_fill(started_ladder(), _fill(1, "0.4"), STEP, hold=False).runtime

    reaction = on_end(partly, order_id(1), AT, rejection=None, hold=False)

    assert reaction.actions == (
        PlaceOrder(
            1, OrderSide.BUY, PRICES[1], Decimal("0.6"), carried_executed=Decimal("0.4")
        ),
    )
    assert reaction.runtime.inventory == Decimal("0.4")
    assert reaction.runtime.levels[1].state is LevelState.EMPTY


def test_the_re_placed_order_counts_what_the_first_executed_toward_its_counter() -> (
    None
):
    partly = on_fill(started_ladder(), _fill(1, "0.4"), STEP, hold=False).runtime
    ended = on_end(partly, order_id(1), AT, rejection=None, hold=False)
    again = perform(ended.runtime, _only_order(ended.actions))

    rest = on_fill(again, _fill(1, "0.6"), STEP, hold=False)

    assert _only_order(rest.actions).quantity == Decimal(1)


def test_a_second_end_at_one_level_within_a_minute_halts() -> None:
    first = on_end(started_ladder(), order_id(1), AT, rejection=None, hold=False)
    again = perform(first.runtime, _only_order(first.actions))

    second = on_end(
        again, order_id(1), AT + timedelta(seconds=59), rejection=None, hold=False
    )

    assert second.actions == (
        Halt(GridReason.LEVEL_KEEPS_ENDING, "L1: two orders ended within a minute"),
    )
    assert second.runtime.reason is GridReason.LEVEL_KEEPS_ENDING


def test_a_second_end_a_minute_later_is_re_placed_again() -> None:
    first = on_end(started_ladder(), order_id(1), AT, rejection=None, hold=False)
    again = perform(first.runtime, _only_order(first.actions))

    second = on_end(
        again, order_id(1), AT + timedelta(minutes=1), rejection=None, hold=False
    )

    assert isinstance(_only_order(second.actions), PlaceOrder)


def test_a_rejection_halts_at_once_with_the_exchange_reason() -> None:
    reaction = on_end(
        started_ladder(), order_id(3), AT, rejection="insufficient balance", hold=False
    )

    assert reaction.actions == (
        Halt(GridReason.ORDER_REJECTED, "L3: insufficient balance"),
    )


def test_a_pause_holds_the_counter_order_and_resume_releases_it() -> None:
    held = on_fill(started_ladder(), _fill(1, "1"), STEP, hold=True)

    assert held.actions == ()
    assert len(held.runtime.held) == 1
    released = release_held(held.runtime)
    assert released.actions == (
        PlaceOrder(2, OrderSide.SELL, PRICES[2], Decimal(1), PRICES[1]),
    )
    assert released.runtime.held == ()


def test_a_counter_aimed_at_a_level_that_holds_an_order_halts() -> None:
    runtime = perform(
        started_ladder(), PlaceOrder(2, OrderSide.BUY, PRICES[2], Decimal(1))
    )

    reaction = on_fill(runtime, _fill(1, "1"), STEP, hold=False)

    assert reaction.actions == (
        Halt(
            GridReason.DUPLICATE_LEVEL_ORDER,
            "L2 already holds an order; the counter of L1 cannot go there",
        ),
    )


def test_a_buy_at_the_top_and_a_sell_at_the_bottom_owe_no_counter() -> None:
    top = perform(empty_ladder(), PlaceOrder(4, OrderSide.BUY, PRICES[4], Decimal(1)))
    bottom = perform(
        empty_ladder(), PlaceOrder(0, OrderSide.SELL, PRICES[0], Decimal(1))
    )

    assert on_fill(top, _fill(4, "1"), STEP, hold=False).actions == ()
    assert on_fill(bottom, _fill(0, "1"), STEP, hold=False).actions == ()


def test_a_refused_placement_empties_its_level() -> None:
    runtime = place_failed(started_ladder(), order_id(0))

    assert runtime.levels[0].state is LevelState.EMPTY
    assert runtime.levels[0].order is None
