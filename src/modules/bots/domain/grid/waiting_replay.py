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

`EPIC-046A` (ADR 046 D5): a plan with a trigger price waits by the same gate the live bot asks
(`entry_gate`): the range, then the trigger. A candle is walked only when it reaches the prices
that open it (`entry_band`), and the probe is planned at the price the bot would enter at
(`entry_price`).

**Stated limit.** The Futures replay has no mark-price history and takes the step's trade close for
the mark, so "the same entry step" holds for the trade-price path, not for a mark that diverges
from it.

The venue's engine is built through the same factory `simulate_grid` is given, so Spot and
Futures (and a third kind) need nothing of their own.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_outcome import (
    FuturesOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    RangeEntry,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_entry_gate import (
    EntryGate,
    entry_band,
    entry_gate,
    entry_price,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.replay_engine import (
    EngineFactory,
    ReplayEngine,
    ReplayOutcome,
)

_ZERO = Decimal(0)


def engine_starting_at(
    build: EngineFactory, params: GridParams, first: PriceBar
) -> ReplayEngine:
    """The engine of a run whose first candle is `first`: the venue's own when its open opens
    the entry gate, a `WaitingReplay` over it otherwise."""
    if _opens(first.open, params):
        return build(first)
    return WaitingReplay(build, params, first)


class WaitingReplay(ReplayEngine):
    """The capital in cash until a step closes where the entry gate opens, then the venue's engine."""

    def __init__(
        self, build: EngineFactory, params: GridParams, first: PriceBar
    ) -> None:
        self._build = build
        self._params = params
        #: Planned where the bot would enter from the first open and never stepped: the ladder the
        #: bot would lay (`plan`) and the shape of an outcome with nothing in it (`outcome`).
        self._probe = build(_at_the_edge(first, params))
        self._inner: ReplayEngine | None = None
        self._entry: RangeEntry | None = None
        #: The candle the bot entered in has not closed yet, and no step of it ran after the entry.
        self._entry_bar_open = False

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
        band_low, band_high = entry_band(self._params)
        return low <= band_high and high >= band_low

    def run_step(self, step: PriceStep) -> None:
        if self._inner is not None:
            self._entry_bar_open = False
            self._inner.run_step(step)
            return
        if step.close is None or step.end is None:
            raise ValueError(
                "a step that a waiting replay judges carries its close and end"
            )
        if _opens(step.close, self._params):
            self._enter(step.end, step.close)

    def close_bar(self, bar: PriceBar, end: datetime) -> None:
        if self._inner is None:
            return
        if self._entry_bar_open:
            # The entry was the last thing in this candle: what the candle traded before it is
            # not what the position saw, so the engine closes it as the price it entered at.
            self._entry_bar_open = False
            held = bar.close
            bar = PriceBar(bar.time, held, held, held, held)
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
        self._entry_bar_open = True
        self._inner = self._build(PriceBar(at, price, price, price, price))


def _opens(price: Decimal, params: GridParams) -> bool:
    return entry_gate(params, price) is EntryGate.OPEN


def _at_the_edge(first: PriceBar, params: GridParams) -> PriceBar:
    price = entry_price(params, first.open)
    return PriceBar(first.time, price, price, price, price)


def _nothing_happened(probe: ReplayOutcome) -> ReplayOutcome:
    """The outcome of a run that placed nothing, built explicitly: only what describes the run
    (the Futures direction, leverage and funding terms) is kept from the probe, so a field added
    to either type later is not inherited from an opening that never happened."""
    futures = probe.futures
    if futures is not None:
        futures = FuturesOutcome(
            direction=futures.direction,
            leverage=futures.leverage,
            funding_included=futures.funding_included,
            funding_note=futures.funding_note,
            funding_paid=_ZERO,
            funding_settlements_charged=0,
            final_position=_ZERO,
            liquidated=False,
            liquidation_price=None,
            margin_lost=_ZERO,
            closest_to_liquidation=None,
        )
    return ReplayOutcome(
        fills=(),
        grid_profit=_ZERO,
        unrealised=_ZERO,
        completed_cycles=0,
        stop_reason=StopReason.END_OF_DATA,
        maker_fees=_ZERO,
        taker_fees=_ZERO,
        final_states=tuple(
            (index, LevelState.EMPTY) for index, _ in probe.final_states
        ),
        average_cost=None,
        stop_detail="",
        futures=futures,
    )
