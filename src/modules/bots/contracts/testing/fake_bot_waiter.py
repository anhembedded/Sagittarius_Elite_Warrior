"""`EPIC-042E` - the fake `IBotWaiter`: a pause moves a fake clock, so a polling caller is tested
without a second thread or a sleep. Verified in `tests/unit/modules/bots/contracts/`."""

from __future__ import annotations

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

    def pause(self, seconds: float) -> None:
        self.pauses += 1
        self._clock.advance(seconds)
