"""`EPIC-029B` — the time a bot's change is stamped with.

A port, not `datetime.now()` in a handler: `created_at` and `run_started_at`
are facts trading will later derive inventory from (ADR D6), so a test must be
able to say exactly what they are.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class IBotClock(ABC):
    """The current time, timezone-aware, in UTC."""

    @abstractmethod
    def now(self) -> datetime:
        """Now, in UTC."""
