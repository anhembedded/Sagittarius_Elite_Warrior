"""`EPIC-035A` — the verified fake `IMonotonicClock`: it says what the test says.

Passes the clock contract with `SystemMonotonicClock`. Adds `advance()`, verified
in `tests/unit/modules/bots/contracts/`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)

FAKE_MONOTONIC_START = 1000.0


class FakeMonotonicClock(IMonotonicClock):
    """Answers a fixed second until a test moves it."""

    def __init__(self, at: float = FAKE_MONOTONIC_START) -> None:
        self._at = at

    def seconds(self) -> float:
        return self._at

    def advance(self, by: float) -> None:
        """Move the clock forward by `by` seconds."""
        self._at += by
