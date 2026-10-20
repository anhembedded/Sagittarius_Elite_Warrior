"""`EPIC-040B` — what any kind's backtest reports: one envelope every pane reads, and one
kind-specific `detail` only the kind's own code reads.

The same shape `FuturesOutcome` already has inside `GridBacktestResult` (`EPIC-039K`): fields every
kind has (the candles replayed, the equity curve against the benchmark, the fills, the fees, what
produced it), **figures** as an ordered list of labelled values so a kind's metrics need no change
in the workbench, **notes** as the caveat sentences, and `detail`, the kind's own rich result
(`GridBacktestResult` for the Grid). This module imports no kind: `test_backtest_outcome_is_kind_neutral.py`.

@par Extension cases (the Grid is the only adapter built, `EPIC-040B`)
  · **Strategy bot** (`EPIC-040G`): its trades are entries and exits, one position at a time, so
    each is a `BacktestFill` with a `label` such as "Enter long" or "Exit", and `maker` false.
  · **DCA** (`EPIC-029L`): scheduled buys are fills with a label; its extra figures (average cost,
    safety orders used) are `BacktestFigure`s.
  · **A kind with no benchmark**: `EquityPoint.benchmark` repeats the starting capital.
Each is one adapter behind `IKindBacktester` and one registration; this file does not change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide

type FigureValue = Decimal | int | datetime | str


class FigureKind(Enum):
    """How the workbench writes and aligns a figure; the UI maps each to its column kind."""

    TIMESTAMP = "timestamp"
    QUANTITY = "quantity"
    MONEY = "money"
    PERCENT = "percent"


class FigureTone(Enum):
    """What a figure means to the reader, for the workbench's meaning colours; a colour is
    never the only signal (`ui-presentation-rule.md` §1), so the figure's sign or words go with it."""

    NEUTRAL = "neutral"
    GOOD = "good"
    BAD = "bad"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class BacktestFigure:
    """One labelled value of a result. `title` carries its unit ("(USDT)"); `value` is raw,
    written by the application's formatter and never formatted here."""

    key: str
    title: str
    kind: FigureKind
    value: FigureValue
    tone: FigureTone = FigureTone.NEUTRAL


@dataclass(frozen=True, slots=True)
class BacktestBar:
    """One candle the replay ran on."""

    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """The bot's value and the benchmark's (buy and hold) at one candle's close."""

    time: datetime
    bot: Decimal
    benchmark: Decimal


@dataclass(frozen=True, slots=True)
class BacktestFill:
    """One simulated execution; `label` is what the trades pane and the chart call it."""

    time: datetime
    side: OrderSide
    price: Decimal
    quantity: Decimal
    fee_quote: Decimal
    label: str
    maker: bool


@dataclass(frozen=True, slots=True)
class DataWindow:
    """The period a replay was asked for, and how much of it was stored."""

    start: datetime
    end: datetime
    expected_candles: int
    stored_candles: int

    @property
    def missing_candles(self) -> int:
        """Candles of the period not stored: not there at all, or gaps."""
        return max(self.expected_candles - self.stored_candles, 0)


@dataclass(frozen=True, slots=True)
class BacktestProvenance:
    """What produced a result (`domain-truth-rule.md`: snapshots carry it)."""

    config: tuple[tuple[str, str], ...]
    maker_fee: Decimal
    taker_fee: Decimal
    first_candle: datetime
    last_candle: datetime
    #: How the replay decided what filled; a sentence the notes repeat.
    fill_rule: str
    #: The period asked for; `None` when the caller replays bars it chose.
    window: DataWindow | None = None


@dataclass(frozen=True, slots=True)
class BacktestOutcome:
    """A whole replay, as the workbench reads it."""

    provenance: BacktestProvenance
    #: The candles replayed (up to the stop), oldest first, for the chart.
    bars: tuple[BacktestBar, ...]
    equity: tuple[EquityPoint, ...]
    fills: tuple[BacktestFill, ...]
    maker_fees: Decimal
    taker_fees: Decimal
    #: Every figure the kind shows, in display order.
    figures: tuple[BacktestFigure, ...]
    #: The caveats that qualify the figures, the most important first.
    notes: tuple[str, ...]
    #: The kind's own result, read only by the kind's own code (a chart overlay, extra panes).
    detail: object
