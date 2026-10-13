"""The hub's nudge to the worker lanes, without losing one.

A plain `Event` shared by several lanes loses wake-ups: the lane that clears it
hides the nudge from the others. A generation counter does not: a lane remembers
the generation it last saw and returns from `wait` as soon as it differs, even
when the nudge came before it started waiting.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_delivery_wakeup import (
    IDeliveryWakeup,
)


class WakeSignal(IDeliveryWakeup):
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._generation = 0

    def notify(self) -> None:
        with self._condition:
            self._generation += 1
            self._condition.notify_all()

    def generation(self) -> int:
        """The generation now; pass it to `wait` as `seen`."""
        with self._condition:
            return self._generation

    def wait(self, seen: int, timeout: float) -> int:
        """Block until the generation differs from `seen` or `timeout` seconds
        pass; the generation then."""
        with self._condition:
            self._condition.wait_for(lambda: self._generation != seen, timeout)
            return self._generation
