"""`IDeliveryWakeup` — the hub telling the worker there is something to send."""

from __future__ import annotations

from abc import ABC, abstractmethod


class IDeliveryWakeup(ABC):
    @abstractmethod
    def notify(self) -> None:
        """Look at the outbox now rather than at the next poll. Never blocks."""
