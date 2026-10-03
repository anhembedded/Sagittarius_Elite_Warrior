"""`EPIC-029B` — the verified fake `IBotClock`: it says what the test says.

Passes `BotClockContract` with `SystemBotClock`. Adds `advance()`, verified in
`tests/unit/modules/bots/contracts/`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock

FAKE_CLOCK_START = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


class FakeBotClock(IBotClock):
    """Answers a fixed instant until a test moves it."""

    def __init__(self, at: datetime = FAKE_CLOCK_START) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at

    def advance(self, by: timedelta) -> None:
        """Move the clock forward by `by`."""
        self._at = self._at + by
