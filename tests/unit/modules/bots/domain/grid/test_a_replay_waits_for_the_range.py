"""`EPIC-044D` (ADR 044 D11) - a replay that starts away from its range waits for it, as the live bot does.

The worked example (60,000-70,000, 10,000 USDT) replayed on hand-built candles whose first open is
below the range. The bot enters at the first 1-second step whose close is inside (the bounds
included), plans and opens at that close, its ladder rests from the next step, no exit is judged
before the entry, equity and the buy-and-hold benchmark are the capital until then, and a window
that never enters has no fill. A Futures replay does the same for every direction.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.fine_klines import (
    FineKlinesByCandle,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    GridBacktestResult,
    RangeEntry,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_figures import (
    grid_notes,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_simulator import (
    GridBacktestInputs,
    simulate_grid,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    position_config,
    schedule,
    settlement,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.futures_replay_builders import (
    replay as futures_replay,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.domain.grid.report_example import (
    CONFIG,
    TERMS,
)

START = datetime(2026, 9, 1, tzinfo=UTC)
MINUTE = timedelta(minutes=1)
D = Decimal
CAPITAL = D(10000)


def _bar(minute: int, o: str, h: str, low: str, c: str) -> PriceBar:
    return PriceBar(START + timedelta(minutes=minute), D(o), D(h), D(low), D(c))


def _kline(minute: int, second: int, price: str, previous: str) -> PriceBar:
    """One second that moved from `previous` to `price`."""
    prices = [D(previous), D(price)]
    return PriceBar(
        START + timedelta(minutes=minute, seconds=second),
        D(previous),
        max(prices),
        min(prices),
        D(price),
    )


#: Minute 0 stays below the range; minute 1 climbs through its lower bound second by second.
_BELOW = _bar(0, "58000", "58500", "57900", "58200")
_CLIMB = _bar(1, "58200", "61000", "58200", "61000")
_CLIMB_SECONDS = (
    _kline(1, 0, "58500", "58200"),
    _kline(1, 1, "59999.99", "58500"),
    _kline(1, 2, "60000", "59999.99"),
    _kline(1, 3, "61000", "60000"),
)
_ENTERED_AT = START + timedelta(minutes=1, seconds=2)
_FINE = {_CLIMB.time: _CLIMB_SECONDS}
#: The range's own bounds are inside it; the price just under the lower bound is not.


def _spot(
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


def test_the_replay_enters_at_the_first_step_that_closes_inside_the_range() -> None:
    result = _spot([_BELOW, _CLIMB], _FINE)

    assert result.waited_for_range
    assert result.range_entry == RangeEntry(_ENTERED_AT, D(60000))


def test_the_bound_itself_is_inside_and_a_price_just_under_it_is_not() -> None:
    """Step 1 closes at 59,999.99 (outside); step 2 at 60,000 (the bound, inside)."""
    result = _spot([_BELOW, _CLIMB], _FINE)

    assert result.range_entry is not None
    assert result.range_entry.time == START + timedelta(minutes=1, seconds=2)


def test_nothing_is_placed_before_the_entry_and_the_opening_trade_is_at_the_entry() -> (
    None
):
    result = _spot([_BELOW, _CLIMB], _FINE)

    first = result.fills[0]
    assert first.time == _ENTERED_AT
    assert (first.side, first.price, first.level_index) == (
        OrderSide.BUY,
        D(60000),
        None,
    )
    assert all(fill.time >= _ENTERED_AT for fill in result.fills)


def test_the_ladder_is_planned_at_the_entry_price() -> None:
    result = _spot([_BELOW, _CLIMB], _FINE)

    assert result.plan.last_price == D(60000)


def test_equity_and_the_benchmark_are_the_capital_until_the_entry() -> None:
    result = _spot([_BELOW, _CLIMB], _FINE)

    before, after = result.equity
    assert before.grid == CAPITAL and before.buy_and_hold == CAPITAL
    assert after.time == _CLIMB.time


def test_the_benchmark_buys_at_the_entry_step_not_at_the_first_candle() -> None:
    """Bought at 58,000 it would read 10,000 x 61,000 / 58,000 = 10,517; bought at the entry's
    60,000 it reads 10,000 x 61,000 / 60,000 = 10,167, less the taker fee."""
    result = _spot([_BELOW, _CLIMB], _FINE)

    held = result.equity[-1].buy_and_hold
    assert math.isclose(held, D("10000") * D(61000) / D(60000), rel_tol=D("0.005"))
    assert held < D(10200)


def test_no_exit_is_judged_before_the_entry() -> None:
    """The stop loss is 57,000 and the first candle trades to 56,000: a bot that held nothing has
    nothing to stop."""
    below_the_stop = _bar(0, "56500", "56800", "56000", "56500")

    result = _spot([below_the_stop, _CLIMB], _FINE)

    assert result.stop_reason is StopReason.END_OF_DATA
    assert result.range_entry is not None


def test_a_window_that_never_enters_has_no_fill_and_flat_equity() -> None:
    result = _spot([_BELOW, _bar(1, "58200", "59000", "58000", "58900")])

    assert result.waited_for_range
    assert result.range_entry is None
    assert result.fills == ()
    assert result.stop_reason is StopReason.END_OF_DATA
    assert result.grid_profit == 0 and result.unrealised == 0
    assert {(p.grid, p.buy_and_hold) for p in result.equity} == {(CAPITAL, CAPITAL)}
    assert result.plan.last_price == D(60000), (
        "the ladder it would lay, at the nearest edge"
    )


def test_a_candle_that_touches_the_range_but_closes_outside_does_not_enter() -> None:
    """Without 1-second klines a candle is one coarse step, judged on its close."""
    touching = _bar(1, "58200", "60500", "58000", "59000")

    result = _spot([_BELOW, touching])

    assert result.range_entry is None
    assert result.coarse_periods == (touching.time,)


def test_a_coarse_candle_that_closes_inside_enters_on_its_close() -> None:
    closing_in = _bar(1, "58200", "61000", "58000", "61000")

    result = _spot([_BELOW, closing_in])

    assert result.range_entry == RangeEntry(closing_in.time, D(61000))
    assert result.coarse_periods == (closing_in.time,)


def test_a_window_that_starts_inside_the_range_does_not_wait() -> None:
    result = _spot([_bar(0, "65000", "65100", "64900", "65000")])

    assert not result.waited_for_range
    assert result.range_entry is None
    assert result.fills[0].time == START


@pytest.mark.parametrize("direction", ["LONG", "SHORT", "NEUTRAL"])
def test_a_futures_replay_waits_and_enters_the_same_way(direction: str) -> None:
    config = position_config(direction)

    result = futures_replay([_BELOW, _CLIMB], config, fine=_FINE)

    assert result.waited_for_range
    assert result.range_entry == RangeEntry(_ENTERED_AT, D(60000))
    assert all(fill.time >= _ENTERED_AT for fill in result.fills)
    assert result.plan.last_price == D(60000)
    before = result.equity[0]
    assert before.grid == CAPITAL and before.buy_and_hold == CAPITAL


@pytest.mark.parametrize("direction", ["LONG", "SHORT", "NEUTRAL"])
def test_a_futures_window_that_never_enters_holds_nothing_and_pays_no_funding(
    direction: str,
) -> None:
    config = position_config(direction)

    result = futures_replay(
        [_BELOW, _bar(1, "58200", "59000", "58000", "58900")],
        config,
        funding=schedule(settlement(1, "0.0003")),
    )

    assert result.range_entry is None and result.fills == ()
    futures = result.futures
    assert futures is not None
    assert futures.final_position == 0 and futures.funding_paid == 0
    assert futures.funding_settlements_charged == 0 and not futures.liquidated


def test_a_futures_replay_charges_only_the_funding_after_the_entry() -> None:
    """A settlement before the entry is not the bot's: it held nothing then."""
    config = position_config("LONG")
    funding = schedule(settlement(0, "0.0003"), settlement(3, "0.0003"))
    later = _bar(3, "61000", "61100", "60900", "61000")

    result = futures_replay([_BELOW, _CLIMB, later], config, funding, fine=_FINE)

    assert result.futures is not None
    assert result.futures.funding_settlements_charged == 1


# -- what the result says --------------------------------------------------- #


def _notes(result: GridBacktestResult) -> str:
    return "\n".join(grid_notes(result))


def test_the_result_says_where_the_bot_entered() -> None:
    notes = _notes(_spot([_BELOW, _CLIMB], _FINE))

    assert "waited and entered at 2026-09-01 00:01:02 UTC, at 60000" in notes
    assert "buy-and-hold benchmark buys at the same step" in notes
    assert "mark-price history" not in notes, "a Spot replay has no mark"


def test_the_result_says_a_window_never_entered_the_range() -> None:
    notes = _notes(_spot([_BELOW]))

    assert "never entered it" in notes and "placed nothing" in notes


def test_a_futures_result_says_the_mark_is_approximated_by_the_trade_close() -> None:
    result = futures_replay([_BELOW, _CLIMB], position_config("SHORT"), fine=_FINE)

    assert "no mark-price history here" in _notes(result)


def test_a_window_that_starts_inside_says_nothing_about_waiting() -> None:
    notes = _notes(_spot([_bar(0, "65000", "65100", "64900", "65000")]))

    assert "waited" not in notes and "outside the range" not in notes
