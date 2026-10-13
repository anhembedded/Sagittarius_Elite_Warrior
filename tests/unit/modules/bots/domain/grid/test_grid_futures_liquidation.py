"""`EPIC-039K` — a Futures replay liquidates the position, and prices it with one formula.

The liquidation price is `estimated_liquidation_price` (trading's, `EPIC-028G`) fed with the
position and margin at the moment asked; these tests recompute it from the replay's own fills
and compare, so a second formula inside the replay would be caught.
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.margin_risk_policy import (
    MarginRiskPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_liquidation import (
    HeldPosition,
    Leveraged,
    distance_to_liquidation,
    isolated_margin,
    liquidation_price,
    loss_of_liquidation,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    PositionBook,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.liquidation_estimate import (
    LiquidationTerms,
    estimated_liquidation_price,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    BRACKETS,
    bar,
    position_config,
    replay,
    schedule,
    settlement,
)

D = Decimal
_QUIET = bar(0, "65000", "65200", "64800", "65000")


def _position_before_the_end(result: GridBacktestResult) -> PositionBook:
    """The book the replay's fills built, without the closing liquidation fill."""
    book = PositionBook(D(0), D(0))
    for fill in result.fills[:-1]:
        book.fill(fill.side, fill.quantity, fill.price)
    return book


def _expected_price(book: PositionBook, leverage: int) -> Decimal | None:
    notional = abs(book.position) * book.entry
    bracket = BRACKETS.bracket_for(notional)
    side = PositionSide.LONG if book.position > 0 else PositionSide.SHORT
    return estimated_liquidation_price(
        LiquidationTerms(
            side,
            abs(book.position),
            book.entry,
            notional / leverage,
            bracket.maintenance_margin_rate,
            bracket.maintenance_amount,
        )
    ).price


# -- the price: one formula ---------------------------------------------------- #


@pytest.mark.parametrize("leverage", [2, 5, 10, 50])
@pytest.mark.parametrize("quantity", [D("0.3"), D("-0.3")])
def test_with_no_maintenance_margin_it_is_the_paper_brokers_formula(
    leverage: int, quantity: Decimal
) -> None:
    """`backtesting`'s `MarginRiskPolicy.liquidation_price` is `entry * (1 -/+ 1/leverage)`,
    which it documents as this formula with a zero maintenance rate and amount. The two agree
    there; they differ only by the maintenance margin, which is why that policy stays as it
    is (its docstring) and nothing here forks the formula."""
    flat = LeverageBrackets(
        "BTCUSDT", (LeverageBracket(1, 125, D(0), D(10**9), D(0), D(0)),)
    )
    held = HeldPosition(quantity, D(65000))

    ours = liquidation_price(held, Leveraged(leverage, flat))

    side = PositionSide.LONG if quantity > 0 else PositionSide.SHORT
    papers = MarginRiskPolicy().liquidation_price(side, float(leverage), 65000.0)
    assert ours is not None and papers is not None
    assert float(ours) == pytest.approx(papers)


def test_the_maintenance_margin_brings_the_price_closer_to_the_entry_than_the_paper_one() -> (
    None
):
    held = HeldPosition(D("0.3"), D(65000))

    with_maintenance = liquidation_price(held, Leveraged(10, BRACKETS))

    assert with_maintenance is not None
    assert D(65000) * D("0.9") < with_maintenance < D(65000)


def test_a_long_at_leverage_one_has_no_liquidation_price() -> None:
    assert (
        liquidation_price(HeldPosition(D("0.3"), D(65000)), Leveraged(1, BRACKETS))
        is None
    )


def test_a_short_at_leverage_one_still_has_one() -> None:
    price = liquidation_price(HeldPosition(D("-0.3"), D(65000)), Leveraged(1, BRACKETS))

    assert price is not None and price > D(65000)


def test_a_flat_position_has_no_price() -> None:
    assert liquidation_price(HeldPosition(D(0), D(0)), Leveraged(5, BRACKETS)) is None


def test_funding_paid_is_taken_from_the_margin_and_brings_the_price_closer() -> None:
    fresh = HeldPosition(D("0.3"), D(65000))
    paid = HeldPosition(D("0.3"), D(65000), funding_paid=D(500))

    assert isolated_margin(paid, 10) == isolated_margin(fresh, 10) - 500
    assert liquidation_price(paid, Leveraged(10, BRACKETS)) > liquidation_price(
        fresh, Leveraged(10, BRACKETS)
    )


def test_the_margin_is_never_negative_whatever_the_funding_paid() -> None:
    drained = HeldPosition(D("0.3"), D(65000), funding_paid=D(10**6))

    assert isolated_margin(drained, 10) == 0


def test_a_higher_bracket_puts_the_price_closer_to_the_entry() -> None:
    small = HeldPosition(D("0.5"), D(65000))  # 32,500: first bracket
    large = HeldPosition(D("5"), D(65000))  # 325,000: third bracket

    near = liquidation_price(small, Leveraged(10, BRACKETS))
    nearer = liquidation_price(large, Leveraged(10, BRACKETS))

    assert near is not None and nearer is not None
    assert D(65000) - nearer < D(65000) - near


def test_the_distance_is_a_fraction_of_the_price_and_zero_past_the_limit() -> None:
    held = HeldPosition(D("0.3"), D(65000))

    assert distance_to_liquidation(D(60000), held, D(54000)) == D(6000) / D(60000)
    assert distance_to_liquidation(D(50000), held, D(54000)) == 0


def test_a_liquidation_loses_exactly_the_margin_whatever_the_close_realised() -> None:
    inside = loss_of_liquidation(D(1000), D(-900))
    gapped = loss_of_liquidation(D(1000), D(-1300))

    assert -900 + inside.realised_adjustment == -1000
    assert -1300 + gapped.realised_adjustment == -1000
    assert inside.margin_lost == gapped.margin_lost == 1000


# -- the run ------------------------------------------------------------------ #


def test_a_long_through_its_liquidation_price_ends_liquidated_with_the_margin_lost() -> (
    None
):
    crash = bar(1, "65000", "65000", "40000", "40000")

    result = replay([_QUIET, crash], position_config("LONG", leverage=10))

    futures = result.futures
    assert futures is not None
    assert result.stop_reason is StopReason.LIQUIDATED
    assert futures.liquidated and futures.final_position == 0
    last = result.fills[-1]
    assert (last.label, last.side, last.fee_quote) == (
        "Liquidation",
        OrderSide.SELL,
        0,
    )
    before = _position_before_the_end(result)
    assert last.quantity == before.position
    # The price is trading's estimate for the position the ladder had built by then.
    assert last.price == _expected_price(before, 10)
    assert futures.liquidation_price == last.price
    margin = abs(before.position) * before.entry / 10
    assert futures.margin_lost == margin
    # The position's whole loss is its margin: what earlier cycles realised, minus the
    # margin, minus the commissions already paid.
    assert result.grid_profit == before.realised - margin - (
        result.maker_fees + result.taker_fees
    )
    assert result.unrealised == 0
    assert result.equity[-1].grid == D(10000) + result.grid_profit
    assert {state for _, state in result.final_states} == {LevelState.EMPTY}
    assert futures.closest_to_liquidation == 0


def test_a_short_through_its_liquidation_price_ends_liquidated() -> None:
    spike = bar(1, "65000", "90000", "65000", "90000")

    result = replay([_QUIET, spike], position_config("SHORT", leverage=10))

    assert result.stop_reason is StopReason.LIQUIDATED
    last = result.fills[-1]
    assert (last.label, last.side) == ("Liquidation", OrderSide.BUY)
    assert last.price == _expected_price(_position_before_the_end(result), 10)


def test_a_wick_that_recovers_within_the_candle_still_liquidates() -> None:
    """The extreme is tested first: the candle closes back at its open, and the position is
    gone all the same."""
    wick = bar(1, "65000", "65100", "40000", "65000")

    result = replay([_QUIET, wick], position_config("LONG", leverage=10))

    assert result.stop_reason is StopReason.LIQUIDATED
    assert result.equity[-1].grid < D(10000)


def test_liquidation_comes_before_a_stop_loss_the_price_reaches_after_it() -> None:
    config = position_config("LONG", leverage=10, stop_loss="percent:5")
    crash = bar(1, "65000", "65000", "40000", "40000")

    result = replay([_QUIET, crash], config)

    assert result.futures is not None and result.futures.liquidation_price is not None
    assert result.futures.liquidation_price > D(57000)
    assert result.stop_reason is StopReason.LIQUIDATED


def test_a_position_that_holds_is_not_liquidated_and_reports_how_close_it_came() -> (
    None
):
    dip = bar(1, "65000", "65000", "60500", "60800")

    result = replay([_QUIET, dip], position_config("LONG", leverage=2))

    futures = result.futures
    assert futures is not None and not futures.liquidated
    assert futures.margin_lost == 0
    assert futures.liquidation_price is None
    assert futures.closest_to_liquidation is not None
    assert 0 < futures.closest_to_liquidation < 1


def test_a_deeper_dip_comes_closer_to_the_liquidation_price() -> None:
    config = position_config("LONG", leverage=5)

    shallow = replay([_QUIET, bar(1, "65000", "65000", "62000", "62000")], config)
    deep = replay([_QUIET, bar(1, "65000", "65000", "56000", "56000")], config)

    assert shallow.futures is not None and deep.futures is not None
    assert shallow.futures.closest_to_liquidation is not None
    assert deep.futures.closest_to_liquidation is not None
    assert deep.futures.closest_to_liquidation < shallow.futures.closest_to_liquidation


def test_a_long_at_leverage_one_never_liquidates_and_reports_no_distance() -> None:
    crash = bar(1, "65000", "65000", "30000", "30000")

    result = replay([_QUIET, crash], position_config("LONG", leverage=1))

    assert result.futures is not None
    assert not result.futures.liquidated
    assert result.futures.closest_to_liquidation is None


def test_funding_that_drains_the_margin_can_liquidate_a_position_the_price_did_not() -> (
    None
):
    drain = schedule(settlement(1, rate="0.5", mark="65000"))

    result = replay(
        [_QUIET, bar(1, "65000", "65100", "64900", "65000")],
        position_config("LONG", leverage=10),
        drain,
    )

    assert result.stop_reason is StopReason.LIQUIDATED
    assert result.futures is not None and result.futures.funding_paid > 0


# -- the property ---------------------------------------------------------------- #


def _walk(seed: int, length: int = 40) -> list:
    rng = random.Random(seed)  # noqa: S311 - a seeded test generator
    price = D(65000)
    bars = []
    for minute in range(length):
        step = D(rng.randrange(-4500, 4501)) / 2
        close = max(price + step, D(30000))
        low = min(price, close) - D(rng.randrange(0, 1500))
        high = max(price, close) + D(rng.randrange(0, 1500))
        bars.append(bar(minute, str(price), str(high), str(max(low, D(1))), str(close)))
        price = close
    return bars


@pytest.mark.parametrize("direction", ["LONG", "SHORT", "NEUTRAL"])
def test_higher_leverage_never_reduces_liquidation_on_the_same_path(
    direction: str,
) -> None:
    """Same candles, same ladder, only the leverage raised: the position scales with it while
    its margin does not, so the liquidation price comes nearer. A run liquidated at one
    leverage is liquidated at every higher one, and no later."""
    leverages = [2, 3, 5, 8, 12, 20]
    for seed in range(40):
        bars = _walk(seed)
        ended_at = {}
        for leverage in leverages:
            result = replay(bars, position_config(direction, leverage=leverage))
            assert result.futures is not None
            liquidated = result.futures.liquidated
            ended_at[leverage] = len(result.bars) if liquidated else None
        previous = None
        for leverage in leverages:
            if previous is not None and ended_at[previous] is not None:
                later = ended_at[leverage]
                assert later is not None and later <= ended_at[previous], (
                    direction,
                    seed,
                    previous,
                    leverage,
                    ended_at,
                )
            previous = leverage


def test_the_walks_of_the_property_do_liquidate_some_runs() -> None:
    """The property above is vacuous if no walk ever liquidates anything."""
    outcomes = {
        replay(_walk(seed), position_config("LONG", leverage=20)).stop_reason
        for seed in range(40)
    }

    assert StopReason.LIQUIDATED in outcomes


def test_funding_paid_on_a_position_does_not_follow_the_next_one_after_it_was_closed() -> (
    None
):
    """A NEUTRAL grid buys, pays a heavy funding, sells back to flat, buys again and crashes.
    The second position's margin is its own initial margin, so it liquidates at exactly the
    estimate for that margin: the first position's funding left with it."""
    bars = [
        _QUIET,
        bar(1, "65000", "65000", "63900", "64000"),  # buys L4 at 64,000
        bar(
            2, "64000", "64000", "63990", "64000"
        ),  # quiet; funding settles at its start
        bar(3, "64000", "65100", "64000", "65100"),  # sells the counter at 65,000: flat
        bar(4, "65100", "65100", "63900", "64000"),  # buys L4 again
        bar(5, "64000", "64000", "40000", "40000"),  # crash
    ]
    heavy = schedule(settlement(2, rate="0.02", mark="64000"))

    result = replay(bars, position_config("NEUTRAL", leverage=10), heavy)

    assert result.stop_reason is StopReason.LIQUIDATED
    assert result.futures is not None and result.futures.funding_paid > 0
    last = result.fills[-1]
    assert last.price == _expected_price(_position_before_the_end(result), 10)
