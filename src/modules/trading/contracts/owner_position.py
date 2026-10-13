"""`EPIC-039D` — what a Futures owner holds: a signed position, derived from
the venue's evidence like Spot's `OwnerInventory` (ADR D6), never supplied.

@details Where Spot counts base held with its cost, a Futures bot holds one
signed quantity on its symbol (One-way mode: positive is long, negative short)
with an average entry. It is replayed from the owner's tagged fills and
**checked against `positionRisk`** rather than replaced by it: `positionRisk`
is account-level and cannot tell the bot's position from one the user opened
(`DECISION` O11). A disagreement is a `PositionDivergence`, reported and never
silently overwritten (`EPIC-021H` §2.4: the exchange wins, and says so).

Funding is not in it: it is a wallet event (`EPIC-039G`). `fees` counts only
what the exchange charged in the quote asset; a fee in another asset (BNB) is
not converted here, since that would mean guessing a price.

Plausible extensions, each a local change: a Hedge-Mode pair of positions
(a second `OwnerPosition` per side behind the same book), a margin figure per
position (one field), funding paid (one field, fed by `EPIC-039G`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

_ZERO = Decimal(0)


@dataclass(frozen=True)
class OwnerPosition:
    """The signed position an owner holds on its symbol."""

    #: Signed: positive long, negative short, zero flat.
    quantity: Decimal
    #: The weighted average price of the position held; `None` when flat.
    average_entry: Decimal | None
    #: Profit made by closing, in the quote asset, before fees.
    realized_pnl: Decimal
    #: Commission paid in the quote asset since the run started.
    fees: Decimal

    def __post_init__(self) -> None:
        if (self.quantity == 0) != (self.average_entry is None):
            raise ValueError(
                "a position has an average entry exactly when it is not flat"
            )


EMPTY_POSITION = OwnerPosition(_ZERO, None, _ZERO, _ZERO)


class PositionDivergenceKind(str, Enum):
    """How the exchange's position differs from the owner's derived one."""

    #: They disagree and the owner's own fills do not explain it.
    POSITION_MISMATCH = "position_mismatch"
    #: They agreed at the last check and the exchange has moved since with no
    #: tagged fill of the owner in between: a forced close, an ADL, or the user
    #: trading by hand. `EPIC-039F`'s guard consumes it.
    POSITION_CHANGED_UNORDERED = "position_changed_unordered"


@dataclass(frozen=True)
class PositionDivergence:
    """One disagreement between the derived position and `positionRisk`."""

    kind: PositionDivergenceKind
    owner_id: str
    tag: str
    symbol: str
    #: What the owner's tagged fills add up to.
    derived: Decimal
    #: What `positionRisk` reports (zero when the position is absent).
    exchange: Decimal

    @property
    def cause(self) -> tuple[Decimal, Decimal]:
        """What makes two divergences the same one, so it is reported once:
        the same two figures, whatever the kind it was first named."""
        return (self.derived, self.exchange)


@dataclass(frozen=True)
class ForeignPosition:
    """A position on the owner's symbol that none of its tagged orders explains.

    @details Reported like Spot's "earlier runs" (`BUG-196`): recorded, never
    counted as the bot's and never traded."""

    symbol: str
    #: Signed, as `positionRisk` reports it.
    quantity: Decimal

    def describe(self) -> str:
        """@brief The refusal in the user's words, with the exchange's quantity
        stripped of its trailing zeros (`0.05000000` reads `0.05`)."""
        direction = "long" if self.quantity > 0 else "short"
        return (
            f"{self.symbol} already has a {direction} position of "
            f"{abs(self.quantity).normalize():f} that this bot did not open; "
            "close it or pick another symbol"
        )
