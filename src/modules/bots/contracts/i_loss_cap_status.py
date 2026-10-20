"""`EPIC-026L` — the loss cap's current status, for a health section or a report."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.loss_cap_status import (
    LossCapStatus,
)


class ILossCapStatus(ABC):
    @abstractmethod
    def status(self) -> LossCapStatus:
        """The cap now: its figure, the day's result and whether it is tripped."""
