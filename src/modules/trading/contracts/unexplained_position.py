"""`BUG-250` — a position the account holds that no claim's history explains, and why.

@details What a refused session opening says about each position it would not excuse, so the
refusal can name the symbol and both figures instead of asking the owner to find the stray.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class PositionUnexplainedWhy(str, Enum):
    """Why a position was not excused."""

    #: No run on this venue claimed the symbol (a stray, or a claim nobody made).
    NO_CLAIM = "no_claim"
    #: A run claimed it, and its tagged history explains a different quantity: more, less, or
    #: the opposite side, beyond one quantity step.
    DIFFERS_FROM_HISTORY = "differs_from_history"
    #: A run claimed it, but its history could not be read or reaches back too far: a position
    #: nobody can verify is not excused.
    HISTORY_UNVERIFIABLE = "history_unverifiable"


@dataclass(frozen=True)
class UnexplainedPosition:
    """One position of the account the opening would not excuse."""

    symbol: str
    #: What `positionRisk` holds on the symbol, signed.
    exchange_quantity: Decimal
    why: PositionUnexplainedWhy
    #: What the claims' tagged history adds up to; `None` when none was derived.
    derived_quantity: Decimal | None = None
