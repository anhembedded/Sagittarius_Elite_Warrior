"""`EPIC-039K` — a Futures Grid replayed on candles: costs, funding, exits and the benchmark.

The report's worked example on a position venue (60,000-70,000 in 10 grids, 10,000 USDT of
margin, 5x), replayed on hand-built candles. Expected figures are written out from the
documented rules (a fee is notional times the rate, a funding charge is position times mark
times rate), not read back from the replay.
"""

from __future__ import annotations

import random
from datetime import timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_funding import (
    no_funding,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import (
    LevelSizing,
    plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_position_model import (
    model_position_along,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    MAKER,
    START,
    TAKER,
    bar,
    kline,
    position_config,
    replay,
    schedule,
    settlement,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    TERMS,
)

D = Decimal
_QUIET = [bar(m, "65000", "65200", "64800", "65000") for m in range(4)]


def _futures(result: GridBacktestResult):
    assert result.futures is not None
    return result.futures


def _opening(result: GridBacktestResult):
    return result.fills[0]


# -- the opening and the costs ---------------------------------------------- #


def test_a_long_opens_with_a_market_buy_at_the_taker_fee() -> None:
    result = replay(_QUIET[:1], position_config("LONG"))

    opening = _opening(result)
    assert (opening.label, opening.side, opening.price) == (
        "Open",
        OrderSide.BUY,
        D(65000),
    )
    assert opening.fee_quote == opening.quantity * D(65000) * TAKER
    assert result.taker_fees == opening.fee_quote
    assert result.maker_fees == 0


def test_a_short_opens_with_a_market_sell_labelled_open() -> None:
    """The Spot reading of the label calls any market SELL an exit."""
    result = replay(_QUIET[:1], position_config("SHORT"))

    assert (_opening(result).label, _opening(result).side) == ("Open", OrderSide.SELL)
    assert _futures(result).final_position == -_opening(result).quantity


def test_a_neutral_grid_opens_nothing() -> None:
    result = replay(_QUIET[:1], position_config("NEUTRAL"))

    assert result.fills == ()
    assert _futures(result).final_position == 0
    assert result.taker_fees == 0


def test_a_ladder_fill_pays_the_maker_fee_and_books_the_closed_quantity() -> None:
    bars = [_QUIET[0], bar(1, "65000", "66100", "64900", "66000")]

    result = replay(bars, position_config("LONG"))

    opening, sell = result.fills[0], result.fills[1]
    assert (sell.label, sell.side, sell.price, sell.maker) == (
        "L6",
        OrderSide.SELL,
        D(66000),
        True,
    )
    fees = opening.quantity * D(65000) * TAKER + sell.quantity * D(66000) * MAKER
    assert result.grid_profit == sell.quantity * D(1000) - fees
    assert (result.maker_fees, result.taker_fees) == (
        sell.quantity * D(66000) * MAKER,
        opening.quantity * D(65000) * TAKER,
    )
    assert result.completed_cycles == 1


def test_the_rows_of_the_ladder_are_the_position_models_on_the_same_prices() -> None:
    """The replay and `grid_position_model` apply the same fill rule to the same plan: on a
    path whose every price is more than a tick from a level (the replay's strict fill rule
    against the model's touch rule), they fill the same levels with the same
    quantities and leave the same position and average entry. This is the replay checked
    against the model; the model against the executor is `EPIC-039H`'s."""
    for direction in ("LONG", "SHORT", "NEUTRAL"):
        config = position_config(direction, leverage=3)
        params = GridParams.from_config(config)
        rng = random.Random(7)  # noqa: S311 - a seeded test generator
        path = [
            D(60000) + D(rng.randrange(1000, 999_000)) / 100 + D("0.005")
            for _ in range(80)
        ]
        # The replay lays the ladder at its first candle's open, so the model must too.
        position_plan = plan(params, TERMS, path[0], LevelSizing.EQUAL_QUANTITY)
        modelled = model_position_along(position_plan, path)
        bars = [bar(i, str(p), str(p), str(p), str(p)) for i, p in enumerate(path)]

        replayed = replay(bars, config)

        ladder = [f for f in replayed.fills if f.level_index is not None]
        assert [(f.level_index, f.side, f.quantity) for f in ladder] == [
            (m.level_index, m.side, m.quantity) for m in modelled.fills
        ]
        assert _futures(replayed).final_position == modelled.position
        assert replayed.average_cost == modelled.entry_price


# -- funding ----------------------------------------------------------------- #


def test_funding_is_charged_at_each_funding_time_on_the_held_position() -> None:
    funding = schedule(
        settlement(1, rate="0.0001", mark="65100"),
        settlement(2, rate="-0.0002", mark="64900"),
    )

    result = replay(_QUIET, position_config("LONG"), funding)

    held = _opening(result).quantity
    expected = held * D(65100) * D("0.0001") + held * D(64900) * D("-0.0002")
    assert _futures(result).funding_paid == expected
    assert _futures(result).funding_settlements_charged == 2


def test_a_short_earns_what_a_long_pays() -> None:
    funding = schedule(settlement(1, rate="0.0001", mark="65000"))

    longs = replay(_QUIET, position_config("LONG"), funding)
    shorts = replay(_QUIET, position_config("SHORT"), funding)

    assert _futures(longs).funding_paid > 0
    assert _futures(shorts).funding_paid == -_futures(longs).funding_paid


def test_a_neutral_grid_holding_nothing_pays_nothing_and_charges_no_settlement() -> (
    None
):
    funding = schedule(settlement(1), settlement(2))

    result = replay(_QUIET, position_config("NEUTRAL"), funding)

    assert _futures(result).funding_paid == 0
    assert _futures(result).funding_settlements_charged == 0


def test_a_settlement_at_the_first_candle_charges_nothing_because_the_position_opens_there() -> (
    None
):
    funding = schedule(settlement(0))

    result = replay(_QUIET, position_config("LONG"), funding)

    assert _futures(result).funding_settlements_charged == 0


def test_a_settlement_in_a_quiet_candle_is_still_charged() -> None:
    """No order is near, so the candle is skipped; funding does not depend on fills."""
    funding = schedule(settlement(2, rate="0.0003", mark="65000"))

    result = replay(_QUIET, position_config("LONG"), funding)

    assert _futures(result).funding_paid == (
        _opening(result).quantity * D(65000) * D("0.0003")
    )


def test_a_record_without_a_mark_price_is_charged_at_the_price_the_replay_last_saw() -> (
    None
):
    funding = schedule(settlement(1, rate="0.0001", mark=None))
    bars = [_QUIET[0], bar(1, "65000", "65100", "64900", "65050"), _QUIET[2]]

    result = replay(bars, position_config("LONG"), funding)

    # The settlement falls at the start of candle 1, so the price in hand is candle 0's close.
    assert _futures(result).funding_paid == (
        _opening(result).quantity * D(65000) * D("0.0001")
    )


def test_funding_is_in_equity_and_never_in_the_grid_profit() -> None:
    funding = schedule(settlement(1, rate="0.001", mark="65000"))

    with_funding = replay(_QUIET, position_config("LONG"), funding)
    without = replay(_QUIET, position_config("LONG"))

    paid = _futures(with_funding).funding_paid
    assert paid > 0
    assert with_funding.grid_profit == without.grid_profit
    assert with_funding.equity[-1].grid == without.equity[-1].grid - paid


def test_a_missing_funding_history_is_stated_not_ignored() -> None:
    note = "The funding history could not be read: the exchange did not answer."

    result = replay(_QUIET, position_config("LONG"), no_funding(note))

    assert _futures(result).funding_included is False
    assert _futures(result).funding_note == note
    assert _futures(result).funding_paid == 0


# -- exits and the order inside a candle -------------------------------------- #


def test_a_stop_loss_closes_the_position_at_market_and_ends_the_run() -> None:
    config = position_config("LONG", leverage=2, stop_loss="percent:5")
    bars = [_QUIET[0], bar(1, "65000", "65000", "56000", "56500")]

    result = replay(bars, config)

    stop = 57000  # 5 % below the 60,000 lower edge
    assert result.stop_reason is StopReason.STOP_LOSS
    assert _futures(result).final_position == 0
    last = result.fills[-1]
    assert (last.label, last.side, last.price) == ("Exit", OrderSide.SELL, D(stop))
    assert last.fee_quote == last.quantity * D(stop) * TAKER
    assert {state for _, state in result.final_states} == {LevelState.EMPTY}


def test_a_stop_loss_closes_a_short_at_market_above_the_range() -> None:
    config = position_config("SHORT", leverage=2, stop_loss="percent:5")
    bars = [_QUIET[0], bar(1, "65000", "74000", "64900", "73800")]

    result = replay(bars, config)

    assert result.stop_reason is StopReason.STOP_LOSS
    assert _futures(result).final_position == 0
    assert result.fills[-1].side is OrderSide.BUY
    assert result.fills[-1].price == D("73500")  # 5 % above the 70,000 upper edge


def test_a_take_profit_closes_a_short_at_market_below_the_range() -> None:
    config = position_config("SHORT", leverage=2, take_profit="percent:5")
    bars = [_QUIET[0], bar(1, "65000", "65100", "56000", "56500")]

    result = replay(bars, config)

    # 57,000 is 5 % below the 60,000 lower edge: the fall covers every reduce-only BUY on the way,
    # so the run ends flat and the take profit has nothing left to close.
    assert result.stop_reason is StopReason.TAKE_PROFIT
    assert _futures(result).final_position == 0
    assert {f.side for f in result.fills if f.label != "Open"} == {OrderSide.BUY}


def test_the_candles_one_second_klines_order_what_the_replay_fills() -> None:
    """The extreme-first pitfall: a candle is not one range. Rising to 66,100 and then falling
    to 64,900 fills the SELL and then the counter BUY it placed; replayed coarse (down, then
    up) the counter is placed in the same step and rests until the next."""
    candle = bar(0, "65000", "66100", "64900", "65000")
    fine = {
        START: (
            kline(0, 0, "65000", "66100", "65000", "66100"),
            kline(0, 1, "66100", "66100", "64900", "64900"),
        )
    }

    ordered = replay([candle], position_config("LONG"), fine=fine)
    coarse = replay([candle], position_config("LONG"))

    assert [f.label for f in ordered.fills] == ["Open", "L6", "L5"]
    assert [f.label for f in coarse.fills] == ["Open", "L6"]
    assert coarse.coarse_periods == (START,)
    assert ordered.coarse_periods == ()


# -- the benchmark ------------------------------------------------------------ #


@pytest.mark.parametrize("direction", ["LONG", "SHORT"])
def test_the_benchmark_holds_what_the_grid_opens(direction: str) -> None:
    result = replay(_QUIET[:1], position_config(direction))

    opening = _opening(result)
    held = opening.quantity if direction == "LONG" else -opening.quantity
    for point in result.equity:
        close = result.bars[0].close
        assert point.buy_and_hold == D(10000) + held * (close - D(65000)) - (
            opening.fee_quote
        )


def test_a_neutral_grid_is_compared_with_idle_capital() -> None:
    result = replay(_QUIET, position_config("NEUTRAL"))

    assert {point.buy_and_hold for point in result.equity} == {D(10000)}


def test_the_benchmark_pays_the_same_funding() -> None:
    funding = schedule(settlement(1, rate="0.001", mark="65000"))

    held = replay(_QUIET, position_config("LONG"), funding)
    free = replay(_QUIET, position_config("LONG"))

    paid = _opening(held).quantity * D(65000) * D("0.001")
    assert held.equity[-1].buy_and_hold == free.equity[-1].buy_and_hold - paid


def test_the_equity_curve_has_a_point_per_candle_replayed() -> None:
    result = replay(_QUIET, position_config("LONG"))

    assert [p.time for p in result.equity] == [
        START + timedelta(minutes=m) for m in range(4)
    ]


def test_a_counter_placed_in_a_step_rests_from_the_next_one() -> None:
    """One 1-second kline that rises through the SELL and falls back through the counter BUY
    it placed completes no round trip: the counter waits for the next step."""
    candle = bar(0, "65000", "66100", "64900", "64950")
    fine = {START: (kline(0, 0, "65000", "66100", "64900", "64950"),)}

    result = replay([candle], position_config("LONG"), fine=fine)

    assert [f.label for f in result.fills] == ["Open", "L6"]
