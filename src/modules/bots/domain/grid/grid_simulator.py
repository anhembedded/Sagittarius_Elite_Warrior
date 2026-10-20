"""`EPIC-029D` — replay a Grid on stored candles, against buy-and-hold (ADR D14, D18).

`simulate_grid` walks the candles oldest first through a `ReplayEngine` (the Spot one unless
the inputs name another, `EPIC-039K`). A candle no resting order or
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

from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestProvenance,
    DataWindow,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_kind_inputs import (
    ExchangeTerms,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.fine_klines import (
    FineKlines,
    NoFineKlines,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    EquityPoint,
    GridBacktestCancelled,
    GridBacktestResult,
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
    ReplaySetup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.replay_engine import (
    EngineFactory,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.spot_replay_engine import (
    SpotReplayEngine,
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
    #: The period the bars were read for, `[start, end]` (the store reads
    #: `start <= open_time <= end`): the result says how many of its candles
    #: were stored. `None` for bars chosen by the caller.
    window: tuple[datetime, datetime] | None = None
    #: What replays the ladder; `None` is the Spot engine. A position venue passes its own
    #: (`EPIC-039K`): the walk over candles, the equity curve and the result are shared.
    engine: EngineFactory | None = None

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
    engine = _engine_for(inputs)(first)
    equity: list[EquityPoint] = []
    coarse: list[datetime] = []
    last = first
    for replayed, bar in enumerate(bars):
        if cancelled():
            return GridBacktestCancelled(replayed, len(bars))
        last = bar
        if engine.may_trade_in(bar.low, bar.high):
            steps = steps_for(
                bar, inputs.fine.within(bar.time, bar.time + inputs.bar_length)
            )
            if steps[0].coarse:
                coarse.append(bar.time)
            for step in steps:
                engine.run_step(step)
                if engine.stopped:
                    break
        engine.close_bar(bar, bar.time + inputs.bar_length)
        equity.append(
            EquityPoint(
                bar.time, engine.value_at(bar.close), engine.benchmark_at(bar.close)
            )
        )
        if engine.stopped:
            break
    outcome = engine.outcome(last.close)
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
        plan=engine.plan,
        bars=bars[: len(equity)],
        equity=tuple(equity),
        fills=outcome.fills,
        grid_profit=outcome.grid_profit,
        unrealised=outcome.unrealised,
        completed_cycles=outcome.completed_cycles,
        stop_reason=outcome.stop_reason,
        maker_fees=outcome.maker_fees,
        taker_fees=outcome.taker_fees,
        coarse_periods=tuple(coarse),
        final_states=outcome.final_states,
        average_cost=outcome.average_cost,
        stop_detail=outcome.stop_detail,
        futures=outcome.futures,
    )


def _engine_for(inputs: GridBacktestInputs) -> EngineFactory:
    """The engine the caller chose, or the Spot one: an inventory venue is the default."""
    if inputs.engine is not None:
        return inputs.engine
    setup = ReplaySetup(inputs.params, inputs.terms)
    return lambda first: SpotReplayEngine(setup, first)


def _data_window(inputs: GridBacktestInputs) -> DataWindow | None:
    if inputs.window is None:
        return None
    start, end = inputs.window
    return DataWindow(
        start=start,
        end=end,
        expected_candles=_closed_candles(start, end, inputs.bar_length),
        stored_candles=sum(
            1
            for bar in inputs.bars
            if start <= bar.time and bar.time + inputs.bar_length <= end
        ),
    )


def _closed_candles(start: datetime, end: datetime, length: timedelta) -> int:
    """The candles that open at or after `start` and close by `end`.

    Candles open on epoch-aligned boundaries (Binance klines up to a day do),
    so a period off the boundaries (13:01 to 13:29 on 15m) expects none and
    never reads as short; a candle still open at `end` is not expected, since
    no sync could have stored it closed (the PR #338 re-review). The stored
    bars are counted in the same set, so the candle opening at `end` (stored,
    perhaps still forming) never hides a real gap (round 3).
    """
    seconds = length.total_seconds()
    first = math.ceil(start.timestamp() / seconds)
    after_last = math.floor(end.timestamp() / seconds)
    return max(after_last - first, 0)
