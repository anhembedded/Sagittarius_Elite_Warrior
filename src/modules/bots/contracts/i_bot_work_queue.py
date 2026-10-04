"""`EPIC-029E` — the one serial queue a running bot's work goes through (ADR D9).

Events arrive on the websocket thread and commands on the UI thread; the bot's
ladder must have exactly one writer. So every handler copies what it heard into
the bot's queue and returns at once, and only the queue's own worker submits,
cancels and writes the store. Tasks run one at a time, in the order posted.

@par Extension cases
  · a priority lane for Stop (a stop overtakes queued placements) — one more
    method here and in the implementation;
  · a queue shared by many bots with per-bot ordering (`EPIC-029J`) — a new
    implementation behind this port;
  · a bounded queue that reports overflow as a fault — a new implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable


class IBotWorkQueue(ABC):
    """Runs posted tasks one after another, off the caller's thread."""

    @abstractmethod
    def post(self, task: Callable[[], None]) -> None:
        """Queue `task`; returns before it runs. A task that raises is logged
        and the queue carries on with the next one."""

    @abstractmethod
    def close(self) -> None:
        """Run what is queued, then stop taking tasks."""
