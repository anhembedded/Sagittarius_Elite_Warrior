"""`EPIC-029D` — what a Grid replay reports (ADR D14, D18).

Every number a user would base a decision on, and what produced it: the fill
rule is part of the result, and so is every candle replayed without 1-second
klines, so no figure stands without its caveat.

· **Grid profit** is what closed cycles earned (`grid_reactions._book_cycle`,
  the live executor's own booking). **Unrealised** is the inventory at the
  last close against its cost. They are kept apart because a grid in a
  falling market shows profit on cycles while it holds losing base.
· **Equity** is quote cash plus the base at each candle's close; the
  buy-and-hold curve sits on the same timestamps (D18).
· **Grid profit on a position venue** (`futures` is set) is the profit of closed cycles net
  of every commission; funding is kept in `futures`, never inside it (`EPIC-039K`).
· **Provenance and the period asked for** are the kind-neutral records (`BacktestProvenance`,
  `DataWindow`): the Grid keeps no copy of them (`EPIC-040F`). Its fills and equity points stay its own,
  which carry the ladder level and the grid's own curve names.
· **Fees** are split by maker (resting ladder orders) and taker (the opening
  buy, an exit), each in the quote asset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.backtest.backtest_outcome import (
    BacktestProvenance,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    FillSide,
    OverlayFill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.futures_outcome import (
    FuturesOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_fill_rule import (
    PriceBar,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_overlay import (
    GridActivity,
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide


class StopReason(str, Enum):
    """Why the replay stopped."""

    END_OF_DATA = "end_of_data"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    #: The ladder halted itself (the live executor would have halted too).
    HALTED = "halted"
    #: A Futures position reached its liquidation price (`EPIC-039K`).
    LIQUIDATED = "liquidated"


@dataclass(frozen=True, slots=True)
class BacktestFill:
    """One simulated fill."""

    time: datetime
    side: OrderSide
    price: Decimal
    quantity: Decimal
    fee_quote: Decimal
    #: `None` for a market order (the opening buy, an exit).
    level_index: int | None
    maker: bool
    #: What to call a market fill when the side does not say it (`EPIC-039K`: a SHORT opens
    #: with a SELL, a liquidation closes at market); `None` keeps the Spot reading.
    tag: str | None = None

    @property
    def label(self) -> str:
        if self.tag is not None:
            return self.tag
        return (
            "Open"
            if self.level_index is None and self.side is OrderSide.BUY
            else ("Exit" if self.level_index is None else f"L{self.level_index}")
        )


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """The grid's and buy-and-hold's value at one candle's close."""

    time: datetime
    grid: Decimal
    buy_and_hold: Decimal


@dataclass(frozen=True, slots=True)
class GridBacktestResult:
    """A whole replay: curves, profit split, fills, fees and caveats."""

    provenance: BacktestProvenance
    plan: GridPlan
    #: The candles replayed (up to the stop), oldest first, for the chart.
    bars: tuple[PriceBar, ...]
    equity: tuple[EquityPoint, ...]
    fills: tuple[BacktestFill, ...]
    grid_profit: Decimal
    unrealised: Decimal
    completed_cycles: int
    stop_reason: StopReason
    maker_fees: Decimal
    taker_fees: Decimal
    #: Candles replayed without 1-second klines, by open time.
    coarse_periods: tuple[datetime, ...]
    #: Each level's state when the replay stopped, for the chart.
    final_states: tuple[tuple[int, LevelState], ...] = ()
    average_cost: Decimal | None = None
    stop_detail: str = ""
    #: The Futures-only figures; `None` for a Spot replay (`EPIC-039K`).
    futures: FuturesOutcome | None = None

    def activity(self) -> GridActivity:
        """What the chart draws on top of the plan (`grid_overlay`)."""
        return GridActivity(
            level_states=dict(self.final_states),
            fills=tuple(
                OverlayFill(
                    fill.time,
                    fill.price,
                    FillSide.BUY if fill.side is OrderSide.BUY else FillSide.SELL,
                    fill.label,
                )
                for fill in self.fills
            ),
            average_cost=self.average_cost,
        )


@dataclass(frozen=True, slots=True)
class GridBacktestCancelled:
    """A replay stopped by its caller: a value, never a partial result."""

    replayed_bars: int
    total_bars: int
