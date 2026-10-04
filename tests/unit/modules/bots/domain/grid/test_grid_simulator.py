"""`EPIC-029D` — the Grid replay's business promises (ADR D14, D18).

The report's worked example (BTC at 65,000; 60,000–70,000 in 10 grids; 10,000
USDT; a 0.1% fee; stop loss 57,000 and take profit 73,500) replayed on
hand-built candles: a level fills only a tick through it, the order inside a
candle comes from its 1-second klines, a counter order waits for the next one,
fees split by maker and taker, every stop reason, and the report's four
regimes as regression fixtures.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.fine_klines import (
    FineKlinesByCandle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestCancelled,
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    FILL_RULE,
    PriceBar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

START = datetime(2026, 9, 1, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
D = Decimal


def _bar(minute: int, o: str, h: str, low: str, c: str) -> PriceBar:
    return PriceBar(START + timedelta(minutes=minute), D(o), D(h), D(low), D(c))


def _kline(minute: int, second: int, o: str, h: str, low: str, c: str) -> PriceBar:
    at = START + timedelta(minutes=minute, seconds=second)
    return PriceBar(at, D(o), D(h), D(low), D(c))


def _replay(
    bars: list[PriceBar],
    fine: dict[datetime, tuple[PriceBar, ...]] | None = None,
    **changes: str,
) -> GridBacktestResult:
    params = GridParams.from_config({**CONFIG, **changes})
    result = simulate_grid(
        GridBacktestInputs(
            params, TERMS, tuple(bars), MINUTE, FineKlinesByCandle(fine or {})
        )
    )
    assert isinstance(result, GridBacktestResult)
    return result


def _ladder_fills(result: GridBacktestResult, side: OrderSide) -> list[Decimal]:
    return [f.price for f in result.fills if f.maker and f.side is side]


# -- the fill rule ---------------------------------------------------------- #


def test_touching_a_level_is_not_a_fill() -> None:
    result = _replay([_bar(0, "65000", "65100", "64000", "64500")])

    assert _ladder_fills(result, OrderSide.BUY) == []


def test_one_tick_through_a_level_fills_it_at_the_level_price() -> None:
    result = _replay([_bar(0, "65000", "65100", "63999.99", "64500")])

    (fill,) = [f for f in result.fills if f.maker]
    assert (fill.side, fill.price, fill.level_index) == (OrderSide.BUY, D(64000), 4)


def test_a_sell_needs_a_tick_above_its_level() -> None:
    touched = _replay([_bar(0, "65000", "66000", "64900", "65500")])
    through = _replay([_bar(0, "65000", "66000.01", "64900", "65500")])

    assert _ladder_fills(touched, OrderSide.SELL) == []
    assert _ladder_fills(through, OrderSide.SELL) == [D(66000)]


def test_one_second_klines_order_a_round_trip_inside_one_candle() -> None:
    """Down through 64,000 then up through 65,000 in two 1-second klines: the
    BUY fills, its counter SELL rests from the next kline and fills there."""
    bar = _bar(0, "65000", "65000.01", "63990", "64990")
    fine = {
        bar.time: (
            _kline(0, 0, "65000", "65000", "63990", "64000"),
            _kline(0, 1, "64000", "65000.01", "64000", "64990"),
        )
    }

    result = _replay([bar], fine)

    assert result.completed_cycles == 1
    assert result.grid_profit > 0
    assert result.coarse_periods == ()


def test_without_fine_data_the_candle_is_coarse_and_completes_no_cycle() -> None:
    """The same candle as one coarse step: down first (adverse), and the
    counter order cannot fill inside the step that placed it."""
    bar = _bar(0, "65000", "65000.01", "63990", "64990")

    result = _replay([bar])

    assert result.completed_cycles == 0
    assert _ladder_fills(result, OrderSide.BUY) == [D(64000)]
    assert result.coarse_periods == (bar.time,)


def test_a_red_kline_visits_its_high_before_its_low() -> None:
    bar = _bar(0, "65000", "66000.01", "63999.99", "64500")
    fine = {bar.time: (_kline(0, 0, "65000", "66000.01", "63999.99", "64500"),)}

    result = _replay([bar], fine)

    sides = [f.side for f in result.fills if f.maker]
    assert sides == [OrderSide.SELL, OrderSide.BUY]


def test_a_candle_nothing_can_react_to_is_not_marked_coarse() -> None:
    result = _replay(
        [
            _bar(0, "65000", "65100", "64900", "65000"),
            _bar(1, "65000", "65200", "64950", "65100"),
        ]
    )

    assert result.coarse_periods == ()
    assert result.provenance.fill_rule == FILL_RULE


# -- fees, equity, buy-and-hold -------------------------------------------- #


def test_the_opening_buy_pays_the_taker_fee_and_ladder_fills_the_maker_fee() -> None:
    result = _replay([_bar(0, "65000", "66000.01", "63999.99", "65000")])

    opening = result.fills[0]
    assert (opening.level_index, opening.maker) == (None, False)
    assert opening.fee_quote == opening.quantity * D("0.001") * D(65000)
    assert result.taker_fees == opening.fee_quote
    ladder = [f for f in result.fills if f.maker]
    assert {f.side for f in ladder} == {OrderSide.BUY, OrderSide.SELL}
    for fill in ladder:
        assert fill.fee_quote == fill.quantity * fill.price * D("0.001")
    assert result.maker_fees == sum(f.fee_quote for f in ladder)


def test_equity_and_buy_and_hold_share_every_timestamp() -> None:
    bars = [_bar(m, "65000", "65100", "64900", "65000") for m in range(3)]

    result = _replay(bars)

    assert [p.time for p in result.equity] == [b.time for b in bars]
    first = result.equity[0]
    # Flat market: each lost only its opening's taker fee, 0.1% of what it
    # bought: about 10 USDT for buy-and-hold (all its capital), about 5 for
    # the grid (half). Step rounding takes a further sliver.
    assert D(9989) < first.buy_and_hold <= D(9990)
    assert D(9994) < first.grid < D(9996)
    assert first.grid > first.buy_and_hold


# -- stop reasons ----------------------------------------------------------- #


def test_the_stop_loss_sells_everything_at_the_stop_price() -> None:
    result = _replay(
        [
            _bar(0, "65000", "65100", "64900", "65000"),
            _bar(1, "65000", "65000", "56000", "56500"),
        ]
    )

    assert result.stop_reason is StopReason.STOP_LOSS
    exit_fill = result.fills[-1]
    assert (exit_fill.side, exit_fill.price, exit_fill.maker) == (
        OrderSide.SELL,
        D(57000),
        False,
    )
    assert all(state is LevelState.EMPTY for _, state in result.final_states)
    assert len(result.equity) == 2


def test_a_candle_that_opens_through_the_stop_exits_at_its_open() -> None:
    result = _replay(
        [
            _bar(0, "65000", "65100", "64900", "65000"),
            _bar(1, "56000", "56500", "55500", "56200"),
        ]
    )

    assert result.stop_reason is StopReason.STOP_LOSS
    assert result.fills[-1].price == D(56000)


def test_the_take_profit_sells_everything_at_its_price() -> None:
    result = _replay(
        [
            _bar(0, "65000", "65100", "64900", "65000"),
            _bar(1, "65000", "74000", "65000", "73800"),
        ]
    )

    assert result.stop_reason is StopReason.TAKE_PROFIT
    assert result.fills[-1].price == D(73500)
    assert result.unrealised < D("0.01")


def test_without_an_exit_the_replay_runs_to_the_last_candle() -> None:
    result = _replay([_bar(m, "65000", "65100", "64900", "65000") for m in range(5)])

    assert result.stop_reason is StopReason.END_OF_DATA
    assert len(result.equity) == 5


def test_a_cancelled_replay_returns_where_it_stopped_not_a_result() -> None:
    params = GridParams.from_config(CONFIG)
    bars = tuple(_bar(m, "65000", "65100", "64900", "65000") for m in range(4))
    asked: list[int] = []

    def cancelled() -> bool:
        asked.append(1)
        return len(asked) > 2

    result = simulate_grid(GridBacktestInputs(params, TERMS, bars, MINUTE), cancelled)

    assert result == GridBacktestCancelled(replayed_bars=2, total_bars=4)


def test_no_candles_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one candle"):
        GridBacktestInputs(GridParams.from_config(CONFIG), TERMS, (), MINUTE)


# -- the report's four regimes (regression fixtures, not real-data claims) -- #


def _path(closes: list[int], wick: int = 50) -> list[PriceBar]:
    bars = []
    previous = closes[0]
    for minute, close in enumerate(closes):
        high = max(previous, close) + wick
        low = min(previous, close) - wick
        bars.append(_bar(minute, str(previous), str(high), str(low), str(close)))
        previous = close
    return bars


def test_ranging_market_earns_cycles_and_beats_holding() -> None:
    swing = [65000, 63000, 67000] * 6 + [65000]

    result = _replay(_path(swing))

    assert result.completed_cycles >= 6
    assert result.grid_profit > 0
    assert result.equity[-1].grid > result.equity[-1].buy_and_hold


def test_uptrend_the_grid_trails_buy_and_hold() -> None:
    climb = list(range(65000, 72001, 500))

    result = _replay(_path(climb), take_profit="off")

    assert result.stop_reason is StopReason.END_OF_DATA
    assert result.equity[-1].grid < result.equity[-1].buy_and_hold


def test_downtrend_the_stop_loss_limits_the_loss() -> None:
    fall = list(range(65000, 49999, -500))

    result = _replay(_path(fall))

    assert result.stop_reason is StopReason.STOP_LOSS
    grid_loss = D(10000) - result.equity[-1].grid
    hold_loss = D(10000) - result.equity[-1].buy_and_hold
    assert D(0) < grid_loss < hold_loss


def test_crash_then_recovery_the_grid_buys_the_dip_and_sells_the_way_up() -> None:
    crash = list(range(65000, 58000, -1000)) + list(range(58000, 65001, 1000))

    result = _replay(_path(crash))

    assert result.stop_reason is StopReason.END_OF_DATA
    assert result.completed_cycles >= 5
    assert result.grid_profit > 0


def test_the_chart_draws_the_replays_fills_and_resting_levels() -> None:
    result = _replay([_bar(0, "65000", "65100", "63999.99", "64500")])

    activity = result.activity()
    labels = [fill.label for fill in activity.fills]
    assert labels == ["Open", "L4"]
    states = dict(result.final_states)
    assert states[4] is LevelState.EMPTY  # its BUY filled
    assert states[5] is LevelState.RESTING_SELL  # the counter SELL rests
    assert states[3] is LevelState.RESTING_BUY
    assert activity.average_cost is not None
