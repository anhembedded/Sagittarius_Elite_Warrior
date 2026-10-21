"""`EPIC-039K` — the port a Grid replay is driven through: what differs between venues.

@details `simulate_grid` walks candles, orders each one's steps from the 1-second klines,
records the equity curve against a benchmark and assembles the result. None of that depends on
whether the venue holds an inventory (Spot) or a position (Futures). What does — the opening
trade, how a fill books, the costs, funding, liquidation, the benchmark — sits behind this
port, one implementation per exposure kind: `SpotReplayEngine` over the unchanged
`GridReplay`, and `FuturesReplay`. A third kind (Coin-M) is one more implementation.

The simulator asks an engine only for what it needs to walk candles; the engine answers
`outcome` once, when the walk ends.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_outcome import (
    FuturesOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_backtest_result import (
    BacktestFill,
    RangeEntry,
    StopReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
    PriceStep,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan


@dataclass(frozen=True, slots=True)
class ReplayOutcome:
    """Everything the result takes from an engine when the walk ends."""

    fills: tuple[BacktestFill, ...]
    grid_profit: Decimal
    unrealised: Decimal
    completed_cycles: int
    stop_reason: StopReason
    maker_fees: Decimal
    taker_fees: Decimal
    final_states: tuple[tuple[int, LevelState], ...]
    average_cost: Decimal | None
    stop_detail: str
    futures: FuturesOutcome | None = None


class ReplayEngine(ABC):
    """One venue kind's ladder, advanced a step at a time."""

    @property
    @abstractmethod
    def plan(self) -> GridPlan:
        """The ladder as it was planned at the first candle's open."""

    @property
    @abstractmethod
    def stopped(self) -> bool:
        """Whether the replay has ended (an exit, a halt, a liquidation)."""

    @property
    def waited_for_range(self) -> bool:
        """Whether the run started away from its range and waited (`waiting_replay.py`)."""
        return False

    @property
    def range_entry(self) -> RangeEntry | None:
        """Where the wait ended; `None` while it has not, or when there was no wait."""
        return None

    @abstractmethod
    def may_trade_in(self, low: Decimal, high: Decimal) -> bool:
        """Could a candle spanning `low`-`high` fill an order, cross an exit or reach a
        liquidation price? Lets the walk skip the 1-second klines of a quiet candle."""

    @abstractmethod
    def run_step(self, step: PriceStep) -> None:
        """Advance through one step."""

    @abstractmethod
    def close_bar(self, bar: PriceBar, end: datetime) -> None:
        """The candle `bar` ended at `end`: book what falls due (funding) and note how close
        the price came to the engine's limits. A venue with nothing due does nothing."""

    @abstractmethod
    def value_at(self, price: Decimal) -> Decimal:
        """The strategy's equity at `price`."""

    @abstractmethod
    def benchmark_at(self, price: Decimal) -> Decimal:
        """The benchmark's equity at `price`, on the same footing as `value_at`."""

    @abstractmethod
    def outcome(self, last_close: Decimal) -> ReplayOutcome:
        """The walk's result figures, the last candle having closed at `last_close`."""


#: Builds the engine of a run from the first candle: how a caller chooses the venue kind.
type EngineFactory = Callable[[PriceBar], ReplayEngine]
