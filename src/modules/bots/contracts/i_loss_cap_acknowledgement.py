"""`EPIC-026L` — the owner's acknowledgement of a tripped account-level loss cap."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ILossCapAcknowledgement(ABC):
    @abstractmethod
    def acknowledge(self) -> bool:
        """Clear a tripped cap, accept the day's loss so far and count again from now; `False`
        when the cap was not tripped. It starts and resumes no bot."""
