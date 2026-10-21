"""`EPIC-044D` - a replay that starts away from its range waits for it, as the live bot does.

@details ADR 044 D11. The live Grid started with the price outside its range places nothing and
waits until a price is inside it (`GridRangeEntry`, `EPIC-044B`); the replay now follows the same
rule through the same definition (`range_position`, the bounds included):

  1. a window whose first candle opens inside the range starts at once, exactly as before
     (`engine_starting_at` builds the engine itself, so the recorded oracles are untouched);
  2. otherwise this engine holds the capital in cash. A candle is walked, 1-second kline by
     1-second kline, when its `[low, high]` reaches the range; the bot **enters at the first step
     whose close is inside** and the venue's own engine is built at that close, planning there and
     opening there, so its ladder rests from the next step. No exit is judged before the entry;
  3. a candle without 1-second klines is one coarse step: it enters on its close if that is
     inside, else not (the result lists it in `coarse_periods`);
  4. equity and the buy-and-hold benchmark are the capital until the entry, and the benchmark
     buys at the entry step too (ADR 044 O3): both are an invested capital;
  5. a window that never enters returns a result with no fill, flat equity and `range_entry`
     `None`, which the result says.

**Stated limit.** The Futures replay has no mark-price history and takes the step's trade close for
the mark, so "the same entry step" holds for the trade-price path, not for a mark that diverges
from it.

The venue's engine is built through the same factory `simulate_grid` is given, so Spot and
Futures (and a third kind) need nothing of their own.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    RangeEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
    PriceStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_params import (
    GridParams,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.range_position import (
    RangePosition,
    range_position,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.replay_engine import (
    EngineFactory,
    ReplayEngine,
    ReplayOutcome,
)

_ZERO = Decimal(0)


def engine_starting_at(
    build: EngineFactory, params: GridParams, first: PriceBar
) -> ReplayEngine:
    """The engine of a run whose first candle is `first`: the venue's own when it opens inside
    the range, a `WaitingReplay` over it otherwise."""
    if _inside(first.open, params):
        return build(first)
    return WaitingReplay(build, params, first)


class WaitingReplay(ReplayEngine):
    """The capital in cash until a step closes inside the range, then the venue's engine."""

    def __init__(
        self, build: EngineFactory, params: GridParams, first: PriceBar
    ) -> None:
        self._build = build
        self._params = params
        #: Planned at the range edge nearest the first open and never stepped: the ladder the
        #: bot would lay (`plan`) and the shape of an outcome with nothing in it (`outcome`).
        self._probe = build(_at_the_edge(first, params))
        self._inner: ReplayEngine | None = None
        self._entry: RangeEntry | None = None

    @property
    def waited_for_range(self) -> bool:
        return True

    @property
    def range_entry(self) -> RangeEntry | None:
        return self._entry

    @property
    def plan(self) -> GridPlan:
        return (self._inner or self._probe).plan

    @property
    def stopped(self) -> bool:
        return self._inner is not None and self._inner.stopped

    def may_trade_in(self, low: Decimal, high: Decimal) -> bool:
        if self._inner is not None:
            return self._inner.may_trade_in(low, high)
        return low <= self._params.upper and high >= self._params.lower

    def run_step(self, step: PriceStep) -> None:
        if self._inner is not None:
            self._inner.run_step(step)
            return
        if step.close is None:
            raise ValueError("a step that a waiting replay judges carries its close")
        if _inside(step.close, self._params):
            self._enter(step.time, step.close)

    def close_bar(self, bar: PriceBar, end: datetime) -> None:
        if self._inner is not None:
            self._inner.close_bar(bar, end)

    def value_at(self, price: Decimal) -> Decimal:
        if self._inner is not None:
            return self._inner.value_at(price)
        return self._params.capital_quote

    def benchmark_at(self, price: Decimal) -> Decimal:
        if self._inner is not None:
            return self._inner.benchmark_at(price)
        return self._params.capital_quote

    def outcome(self, last_close: Decimal) -> ReplayOutcome:
        if self._inner is not None:
            return self._inner.outcome(last_close)
        return _nothing_happened(self._probe.outcome(last_close))

    def _enter(self, at: datetime, price: Decimal) -> None:
        """Build the venue's engine at the closing price of the step that entered: it plans and
        opens there, and the step itself is not replayed through it (the ladder rests from the
        next one)."""
        self._entry = RangeEntry(at, price)
        self._inner = self._build(PriceBar(at, price, price, price, price))


def _inside(price: Decimal, params: GridParams) -> bool:
    return range_position(price, params.lower, params.upper) is RangePosition.INSIDE


def _at_the_edge(first: PriceBar, params: GridParams) -> PriceBar:
    price = min(max(first.open, params.lower), params.upper)
    return PriceBar(first.time, price, price, price, price)


def _nothing_happened(probe: ReplayOutcome) -> ReplayOutcome:
    """The probe's outcome with everything the opening would have put in it taken out."""
    futures = probe.futures
    if futures is not None:
        futures = replace(
            futures,
            funding_paid=_ZERO,
            funding_settlements_charged=0,
            final_position=_ZERO,
            liquidated=False,
            liquidation_price=None,
            margin_lost=_ZERO,
            closest_to_liquidation=None,
        )
    return replace(
        probe,
        fills=(),
        grid_profit=_ZERO,
        unrealised=_ZERO,
        completed_cycles=0,
        maker_fees=_ZERO,
        taker_fees=_ZERO,
        final_states=tuple(
            (index, LevelState.EMPTY) for index, _ in probe.final_states
        ),
        average_cost=None,
        stop_detail="",
        futures=futures,
    )
