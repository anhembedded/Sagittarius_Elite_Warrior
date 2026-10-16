"""`EPIC-039L` — what keeps a Grid's exposure protected while the app cannot watch it, per venue profile.

@details A Futures position left alone is a leveraged exposure whose loss grows with the move; the
only protection that survives a dead app is an order resting on the exchange. This port is the
Grid's one seam to it, the same shape as `IOpeningStrategy` and `IExposureCloser`:

  · `protect` — right after the opening, before the ladder is laid: the stop stands, its id
    saved first. `False`: it could not, the bot has already moved (`fail_with`) and the start
    returns;
  · `supervise` — on the price watch's beat and after a reconcile: a stop that vanished is
    placed again, a missing one is placed, one standing over a flat symbol is cancelled, one that
    triggered is said (`ProtectionVerdict.TRIGGERED`);
  · `release` — once the bot's own exposure is closed (`ProtectedCloser`): the stops are
    cancelled. `False`: one could not be, and the stop waits.

Spot has none (`NoProtection`). Decision record `DECISION_2026-10-16`, D4 to D8.

Plausible extensions, each a local change: a take profit on the exchange (O3) is a second order
of the same kind in the service's list; a Coin-M venue is its own implementation; the halt
policy that leaves a position under a standing stop (`EPIC-039L` C3) asks the service whether
one stands, one more method here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan


class ProtectionVerdict(str, Enum):
    """What one look at the stops found."""

    #: Nothing the bot must act on (the stops stand, or none is wanted, or the exchange could not
    #: be read this time and the next look tries again).
    OK = "ok"
    #: A stop triggered: the exchange closed the position. The bot stops with that reason.
    TRIGGERED = "triggered"


class IExposureProtection(ABC):
    @abstractmethod
    def protect(self, plan: GridPlan) -> bool:
        """Have the stop stand over the opening exposure of `plan`, its id saved first.

        @return `False` when it could not stand; the bot has then already moved."""

    @abstractmethod
    def supervise(self) -> ProtectionVerdict:
        """Look at the stops against the exchange and the position, and put right what can be."""

    @abstractmethod
    def release(self) -> bool:
        """Cancel the stops: the bot's own exposure is closed.

        @return `False` when a stop is still standing because its cancel did not go through."""
