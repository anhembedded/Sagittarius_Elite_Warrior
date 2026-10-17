"""`EPIC-042E` - the fake `IBotWaiter` moves the fake clock by what was asked and counts the pauses."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_waiter import (
    FakeBotWaiter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
)


def test_a_pause_moves_the_fake_clock_by_the_seconds_asked() -> None:
    clock = FakeMonotonicClock()
    waiter = FakeBotWaiter(clock)
    start = clock.seconds()

    waiter.pause(0.25)
    waiter.pause(1.0)

    assert clock.seconds() - start == 1.25
    assert waiter.pauses == 2
