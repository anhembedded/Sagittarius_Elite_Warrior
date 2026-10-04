"""`EPIC-029B`, `EPIC-029G` — what a bot kind asks its chart to draw (ADR D2, D16).

Data only, Qt-free: horizontal price lines with a role and a label, price
bands, and the bot's fills. A kind computes it; the one drawer in `bots/ui`
turns it into chart items the same way for the planner preview, the backtest
result and the running bot (ADR D16), so the three can never draw a bot
differently. A role decides how an item is drawn, so a new kind reuses the
drawer by reusing roles, and a new role is one entry in the drawer's style
table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class OverlayRole(str, Enum):
    """What a price line means, which decides how it is drawn."""

    BUY_LEVEL = "BUY_LEVEL"
    SELL_LEVEL = "SELL_LEVEL"
    EMPTY_LEVEL = "EMPTY_LEVEL"
    #: A level whose resting order has partly filled.
    PARTIAL_LEVEL = "PARTIAL_LEVEL"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    #: The lower or upper limit of the range the user chose.
    RANGE_EDGE = "RANGE_EDGE"
    #: The average cost of what the bot holds.
    AVERAGE_COST = "AVERAGE_COST"


class OverlayBandRole(str, Enum):
    """What a price band suggests, which decides how it is drawn."""

    #: Where a range edge sits if the range is the report's 2–4 daily ATRs.
    ATR_ZONE = "ATR_ZONE"
    #: Between the Bollinger bands.
    BOLLINGER = "BOLLINGER"


class FillSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


@dataclass(frozen=True, slots=True)
class OverlayLine:
    """One horizontal price line."""

    price: Decimal
    role: OverlayRole
    label: str


@dataclass(frozen=True, slots=True)
class OverlayBand:
    """One horizontal band between two prices."""

    lower: Decimal
    upper: Decimal
    role: OverlayBandRole
    label: str

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise ValueError("a band's lower price is above its upper price")


@dataclass(frozen=True, slots=True)
class OverlayFill:
    """One fill of the bot's order, drawn where and when it traded."""

    time: datetime
    price: Decimal
    side: FillSide
    label: str


@dataclass(frozen=True, slots=True)
class BotOverlay:
    """Everything one bot draws on its chart: lines lowest price first, bands
    lowest first, fills oldest first."""

    lines: tuple[OverlayLine, ...] = ()
    bands: tuple[OverlayBand, ...] = ()
    fills: tuple[OverlayFill, ...] = ()
