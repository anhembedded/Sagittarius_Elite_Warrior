"""`EPIC-039H` — how a Grid's start takes its opening exposure, per venue profile.

@details Everything in the start is shared except this: Spot buys the base the SELL levels
will sell, in slices, and sizes those SELLs net of the fee the buy took from the base; a
position venue sends the plan's signed opening quantity as market orders and sizes nothing
net, because a position's fee is paid in the quote asset. The strategy also has trading count
what it did from the exchange's own record (ADR D6) before the ladder is laid, so a ladder is
never laid over an opening the exchange does not show.

`open` answers the ladder to lay, or that the start stopped: the bot has then already moved
(`fail_with`) and the sequence only returns.

Plausible extensions, each a local change: a SHORT or NEUTRAL opening (`EPIC-039I`) is one
more strategy, or the same one reading the sign of `GridPlan.opening_quantity`; a start
with no opening at all is a strategy whose `open` returns `plan` untouched.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan


@dataclass(frozen=True, slots=True)
class OpeningResult:
    """The ladder to lay once the opening is done, or `None`: the start stopped, and the bot
    already carries the reason."""

    ladder: GridPlan | None

    @property
    def proceeds(self) -> bool:
        return self.ladder is not None


class IOpeningStrategy(ABC):
    @abstractmethod
    def open(self, plan: GridPlan) -> OpeningResult:
        """Take `plan`'s opening exposure and have it counted from the exchange's record.

        @return The ladder to lay, which may differ from `plan` (Spot's SELLs net of the
        fee); `ladder is None` when the start stopped."""
