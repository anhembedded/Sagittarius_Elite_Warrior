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
· **Fees** are split by maker (resting ladder orders) and taker (the opening
  buy, an exit), each in the quote asset.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    FillSide,
    OverlayFill,
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

    @property
    def label(self) -> str:
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
class BacktestProvenance:
    """What produced a result (`domain-truth-rule.md`: snapshots carry it)."""

    config: tuple[tuple[str, str], ...]
    maker_fee: Decimal
    taker_fee: Decimal
    first_candle: datetime
    last_candle: datetime
    fill_rule: str


@dataclass(frozen=True, slots=True)
class GridBacktestResult:
    """A whole replay: curves, profit split, fills, fees and caveats."""

    provenance: BacktestProvenance
    plan: GridPlan
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
