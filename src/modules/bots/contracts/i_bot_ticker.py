"""`EPIC-035A` — a periodic trigger a bots service runs a check on.

The price watch asks every bot, every few seconds, whether its feed went quiet.
The trigger is a port, not a `threading.Timer` in the service, so a test fires
it on demand and nothing sleeps (`testing-rule.md` §2).

@par Extension cases
  · the user-data stream's health check (`EPIC-035B`) and a heartbeat
    (`EPIC-035K`) are one more `every()` on the same implementation;
  · a ticker driven by the Qt event loop, if a check ever needs the UI thread —
    a new implementation behind this port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class IBotTicker(ABC):
    """Runs a task every so many seconds until closed."""

    @abstractmethod
    def every(self, seconds: float, task: Callable[[], None]) -> None:
        """Run `task` every `seconds`, the first time `seconds` from now. A task
        that raises is logged and the next tick still comes. Calling it again
        adds another task; a task never overlaps itself."""

    @abstractmethod
    def close(self) -> None:
        """Stop ticking; a task already running finishes. Safe to call twice."""
