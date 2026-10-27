"""`EPIC-047C` — the host-facts file, as the bridge looks at it. Implemented by `operations` (`modules/operations/link.py`)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    FactsLook,
)


class IBridgeFacts(ABC):
    @abstractmethod
    def look(self) -> FactsLook:
        """Read the file again; a torn, older or missing one never replaces the last good document."""
