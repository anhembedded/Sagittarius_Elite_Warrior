"""`EPIC-035C` — the verified fake `IBotRetryScheduler`: time moves when the test says.

Passes `BotRetrySchedulerContract` with `TimerBotRetryScheduler`. Adds
`pending` and `run_next()`, verified in `tests/unit/modules/bots/contracts/`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)


@dataclass(frozen=True, slots=True)
class ScheduledRetry:
    """One retry waiting for its time."""

    delay: timedelta
    task: Callable[[], None]


class FakeBotRetryScheduler(IBotRetryScheduler):
    """Holds what was scheduled until a test runs it."""

    def __init__(self) -> None:
        self.pending: list[ScheduledRetry] = []
        self._closed = False

    def after(self, delay: timedelta, task: Callable[[], None]) -> None:
        if not self._closed:
            self.pending.append(ScheduledRetry(delay, task))

    def close(self) -> None:
        self._closed = True
        self.pending.clear()

    def run_next(self) -> None:
        """Run the oldest pending retry, as if its time had come."""
        self.pending.pop(0).task()
