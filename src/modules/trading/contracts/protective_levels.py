"""`EPIC-028I` — the take-profit and stop-loss prices a user (or, with
`EPIC-026K`, a strategy) asks to protect a position with.

@details Either may be left out, not both: protection with neither is no
protection. Whether each sits on the right side of the entry is
`protection_problem`'s answer, because that depends on the entry's side.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.estimate_inputs import (
    require_positive,
)


@dataclass(frozen=True)
class ProtectiveLevels:
    """The trigger prices of a position's protective orders."""

    take_profit: Decimal | None
    stop_loss: Decimal | None

    def __post_init__(self) -> None:
        if self.take_profit is None and self.stop_loss is None:
            raise ValueError("protection needs a take-profit, a stop-loss or both")
        if self.take_profit is not None:
            require_positive("take_profit", self.take_profit)
        if self.stop_loss is not None:
            require_positive("stop_loss", self.stop_loss)
