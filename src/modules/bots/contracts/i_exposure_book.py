"""`EPIC-039D` — what a bot holds, asked one way on Spot and on Futures.

@details A bot's executor asks one question, `held()`, and a Spot and a
Futures answer differ only in kind: an `INVENTORY` quantity is the base the bot
bought and still holds (never negative), a `POSITION` quantity is signed
(positive long, negative short). Both are derived by trading from the venue's
history of the bot's tagged orders and never supplied by the bot (ADR D6,
`DECISION` O11); a bot reads it from the answer of its budget registration,
which derives it again, so a stale figure is replaced by registering, not by
asking the bot's own record.

Plausible extensions, each a local change: `headroom()` (what the bot may still
add, `EPIC-039H` when the Futures executor needs it), a third kind behind
`ExposureKind` and one more adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    ExposureKind,
)


@dataclass(frozen=True)
class Exposure:
    """What a bot holds on its symbol."""

    kind: ExposureKind
    #: Base held: not negative for an inventory, signed for a position.
    quantity: Decimal
    #: The average price of what is held; `None` when nothing is held.
    average_entry: Decimal | None

    def __post_init__(self) -> None:
        if self.kind is ExposureKind.INVENTORY and self.quantity < 0:
            raise ValueError("an inventory is never negative")
        if (self.quantity == 0) != (self.average_entry is None):
            raise ValueError(
                "an exposure has an average entry exactly when it holds something"
            )

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0


class IExposureBook(ABC):
    """What the bot holds now."""

    @abstractmethod
    def held(self) -> Exposure:
        """@brief The bot's holding as trading last derived it from the venue."""
