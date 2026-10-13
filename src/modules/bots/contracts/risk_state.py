"""`EPIC-039F` - what a running position bot's risk guard is told and what it answers.

@details `RiskSnapshot` is what the **exchange reports** (its liquidation price, the mark
price, the signed position) and when it was read; the guard never computes the liquidation
price at run time, it compares the reported one with the mark (liquidation is on mark).
`RiskState` is the answer. Four levels, not three: a snapshot too old to say anything is
`UNKNOWN`, which is never `SAFE` (the `ExchangeSnapshot` three-state pattern).

The exchange's margin ratio is not in the snapshot: neither `positionRisk` nor the account
read the app makes carries it, so a `MARGIN_LOW` alert has no source yet (it needs a reader
first; see the task's alert proposal).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    WARN = "warn"
    CRITICAL = "critical"
    #: The snapshot is stale or lacks the figure the judgement needs.
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RiskSnapshot:
    """The exchange's word on the bot's symbol, at one moment."""

    #: Signed: positive long, negative short, zero flat.
    position: Decimal
    mark_price: Decimal
    #: As reported; `None` when the exchange reports none for a position.
    liquidation_price: Decimal | None
    taken_at: datetime

    def __post_init__(self) -> None:
        if self.mark_price <= 0:
            raise ValueError("mark_price must be positive")
        if self.taken_at.tzinfo is None:
            raise ValueError("a risk snapshot needs a timezone-aware instant")


@dataclass(frozen=True, slots=True)
class RiskState:
    level: RiskLevel
    #: A sentence a person can read, with the measured figure.
    reason: str
    #: |mark - liquidation| / mark; `None` when it could not be measured.
    distance: Decimal | None = None
