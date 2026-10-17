"""`EPIC-042E` - the fake `IBotWaiter`: a pause moves a fake clock and runs what the test hooks in.

The hook stands for the worker finishing its task while the caller waits (a proposal appearing),
so a polling caller is tested without a second thread or a sleep.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_waiter import (
    IBotWaiter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
)


class FakeBotWaiter(IBotWaiter):
    def __init__(self, clock: FakeMonotonicClock) -> None:
        self._clock = clock
        self.pauses = 0
        #: Called after each pause with how many there have been; a test sets it.
        self.on_pause: Callable[[int], None] = lambda _count: None

    def pause(self, seconds: float) -> None:
        self.pauses += 1
        self._clock.advance(seconds)
        self.on_pause(self.pauses)
