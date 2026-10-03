"""`EPIC-029B` — `IBotClock` on the system clock."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock


class SystemBotClock(IBotClock):
    """`datetime.now(UTC)`."""

    def now(self) -> datetime:
        return datetime.now(UTC)
