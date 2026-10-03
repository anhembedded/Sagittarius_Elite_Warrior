"""`EPIC-029B` — what a bot kind asks its chart to draw (ADR D2, D16).

Data only: price lines with a role and a label. The kind computes it, Qt-free;
the drawer in `bots/ui` (`EPIC-029G`) turns it into chart items, the same way
for the planner, the backtest and the running bot.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class OverlayRole(str, Enum):
    """What a price line means, which decides how it is drawn."""

    BUY_LEVEL = "BUY_LEVEL"
    SELL_LEVEL = "SELL_LEVEL"
    EMPTY_LEVEL = "EMPTY_LEVEL"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"


@dataclass(frozen=True, slots=True)
class OverlayLine:
    """One horizontal price line."""

    price: Decimal
    role: OverlayRole
    label: str


@dataclass(frozen=True, slots=True)
class BotOverlay:
    """Everything one bot draws on its chart, lowest price first."""

    lines: tuple[OverlayLine, ...] = ()
