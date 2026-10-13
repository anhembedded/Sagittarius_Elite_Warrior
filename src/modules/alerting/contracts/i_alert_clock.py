"""`IAlertClock` — the time the module reads, injected so no test sleeps."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class IAlertClock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """The current instant: timezone-aware, in UTC, never earlier than an
        earlier answer."""
