"""`EPIC-039F` - what a running bot's risk watch reads from the exchange.

@details Two narrow roles, because the watch uses them at different moments: a fresh
`RiskSnapshot` for the distance check, and a second look at a position divergence before the
bot halts on it. The adapters are `EPIC-039H`'s (trading's `positionRisk`, mark price and the
owner's position book); this module only names what the watch needs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import RiskSnapshot
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_position import (
    PositionDivergence,
)


class RiskReadError(Exception):
    """The exchange could not be read for the risk watch; it says nothing about the risk."""


class IRiskSnapshotSource(ABC):
    @abstractmethod
    def read(self) -> RiskSnapshot:
        """@return The exchange's position, mark price and liquidation price now.
        @raise RiskReadError A failed read; the watch keeps its last snapshot, which ages."""


class IPositionRecheck(ABC):
    @abstractmethod
    def recheck(self, divergence: PositionDivergence) -> PositionDivergence | None:
        """@return The divergence as `positionRisk` and the owner's book show it now, or
        `None` when they agree again (the stream delivered the matching fill).
        @raise RiskReadError A failed read; the watch asks again at its next beat."""
