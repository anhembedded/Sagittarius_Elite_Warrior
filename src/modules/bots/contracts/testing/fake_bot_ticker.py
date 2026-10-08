"""`EPIC-035A` — the verified fake `IBotTicker`: it ticks when the test says.

Adds `fire()`, `interval` and `closed`, verified in
`tests/unit/modules/bots/contracts/`.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_ticker import (
    IBotTicker,
)


class FakeBotTicker(IBotTicker):
    """Holds the tasks it was given and runs them, in order, on `fire()`."""

    def __init__(self) -> None:
        self._tasks: list[Callable[[], None]] = []
        self.interval: float | None = None
        self.closed = False

    def every(self, seconds: float, task: Callable[[], None]) -> None:
        self.interval = seconds
        self._tasks.append(task)

    def close(self) -> None:
        self.closed = True

    def fire(self) -> None:
        """One tick of the interval: run every task, unless closed."""
        if self.closed:
            return
        for task in tuple(self._tasks):
            task()
