"""`EPIC-029D` — replay a Grid on stored candles, against buy-and-hold (ADR D14, D18).

`simulate_grid` walks the candles oldest first. A candle no resting order or
exit could react to is skipped, 1-second klines and all; one that could is
replayed through its 1-second klines, or, without klines spanning its low and
high, as one coarse step, listed in `coarse_periods`. After each candle the grid's equity and the
buy-and-hold value at its close are recorded on the same timestamp.

The replay stops at the last candle (`END_OF_DATA`), at an exit (`STOP_LOSS`,
`TAKE_PROFIT`), or when the ladder halts itself (`HALTED`, with the live
executor's own reason). `cancelled` is asked before every candle; a cancelled
replay returns `GridBacktestCancelled`, never a partial result.

Pure: no clock, no I/O, no threads. The application layer loads the candles
and runs this on a worker.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.buy_and_hold import (
    buy_and_hold,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.fine_klines import (
    FineKlines,
    NoFineKlines,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    BacktestProvenance,
    DataWindow,
    EquityPoint,
    GridBacktestCancelled,
    GridBacktestResult,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    FILL_RULE,
    PriceBar,
    steps_for,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_replay import (
    GridReplay,
    ReplaySetup,
)


@dataclass(frozen=True, slots=True)
class GridBacktestInputs:
    """A replay's whole input (`code/quality.md` §7)."""

    params: GridParams
    terms: ExchangeTerms
    #: The candles the result is shown on, oldest first, all one length.
    bars: tuple[PriceBar, ...]
    bar_length: timedelta
    #: Where each reactive candle's 1-second klines come from.
    fine: FineKlines = field(default_factory=NoFineKlines)
    #: The period the bars were read for, `[start, end)`: the result says how
    #: many of its candles were stored. `None` for bars chosen by the caller.
    window: tuple[datetime, datetime] | None = None

    def __post_init__(self) -> None:
        if not self.bars:
            raise ValueError("a Grid backtest needs at least one candle")
        if self.bar_length <= timedelta(0):
            raise ValueError("bar_length must be positive")


def _never() -> bool:
    return False


def simulate_grid(
    inputs: GridBacktestInputs, cancelled: Callable[[], bool] = _never
) -> GridBacktestResult | GridBacktestCancelled:
    """@brief The replay of `inputs`, or the point it was cancelled at."""
    bars = inputs.bars
    first = bars[0]
    replay = GridReplay(ReplaySetup(inputs.params, inputs.terms), first)
    hold = buy_and_hold(
        inputs.params.capital_quote,
        first.open,
        inputs.terms.taker_fee,
        inputs.terms.step_size,
    )
    equity: list[EquityPoint] = []
    coarse: list[datetime] = []
    last = first
    for replayed, bar in enumerate(bars):
        if cancelled():
            return GridBacktestCancelled(replayed, len(bars))
        last = bar
        if replay.may_trade_in(bar.low, bar.high):
            steps = steps_for(
                bar, inputs.fine.within(bar.time, bar.time + inputs.bar_length)
            )
            if steps[0].coarse:
                coarse.append(bar.time)
            for step in steps:
                replay.run_step(step)
                if replay.stop is not None:
                    break
        equity.append(
            EquityPoint(bar.time, replay.value_at(bar.close), hold.value_at(bar.close))
        )
        if replay.stop is not None:
            break
    runtime = replay.runtime
    return GridBacktestResult(
        provenance=BacktestProvenance(
            config=tuple(sorted(inputs.params.to_config().items())),
            maker_fee=inputs.terms.maker_fee,
            taker_fee=inputs.terms.taker_fee,
            first_candle=first.time,
            last_candle=last.time,
            fill_rule=FILL_RULE,
            window=_data_window(inputs),
        ),
        plan=replay.plan,
        bars=bars[: len(equity)],
        equity=tuple(equity),
        fills=tuple(replay.fills),
        grid_profit=runtime.realised_profit,
        unrealised=runtime.inventory * last.close - runtime.cost,
        completed_cycles=runtime.completed_cycles,
        stop_reason=replay.stop or StopReason.END_OF_DATA,
        maker_fees=replay.maker_fees,
        taker_fees=replay.taker_fees,
        coarse_periods=tuple(coarse),
        final_states=replay.drawn_states(),
        average_cost=runtime.average_cost,
        stop_detail=replay.stop_detail,
    )


def _data_window(inputs: GridBacktestInputs) -> DataWindow | None:
    if inputs.window is None:
        return None
    start, end = inputs.window
    return DataWindow(
        start=start,
        end=end,
        expected_candles=math.ceil((end - start) / inputs.bar_length),
        stored_candles=len(inputs.bars),
    )
