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

    #: The opening offered no claim at all (a Start, an arm, a manual order): only a bot's own
    #: Resume or Stop excuses a position, and the position may well be a waiting bot's.
    NO_CLAIM_OFFERED = "no_claim_offered"
    #: Claims were offered and none names this symbol (a stray, or a position opened by hand).
    NO_CLAIM = "no_claim"
    #: A run claimed it, and its tagged history explains a different quantity: more, less, or
    #: the opposite side, by any amount.
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
