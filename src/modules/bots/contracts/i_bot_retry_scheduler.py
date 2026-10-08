"""`EPIC-035C` — the seam a bot's bounded retries wait on (ADR D9).

A stop that waited on the exchange (a refused cancel, an order not yet gone)
retries on a schedule, with no session event to wake it. The executor owns the
decision to retry; this port owns only the waiting, so a test advances time by
hand and the app waits on a real timer.

@par Extension cases
  · a retry for another waiting state (a refused resume read) — one more call
    site on this port, no new port;
  · a shared timer thread for many bots — a new implementation behind this port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import timedelta


class IBotRetryScheduler(ABC):
    """Runs a task once, later, off the caller's thread."""

    @abstractmethod
    def after(self, delay: timedelta, task: Callable[[], None]) -> None:
        """Run `task` once, no earlier than `delay` from now. The task only
        posts to a bot's queue: it must not touch a bot's record itself.
        Ignored once the scheduler is closed."""

    @abstractmethod
    def close(self) -> None:
        """Cancel everything pending and ignore later calls (module shutdown)."""
