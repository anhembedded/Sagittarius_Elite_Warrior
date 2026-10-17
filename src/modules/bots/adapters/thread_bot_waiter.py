"""`EPIC-042E` - the real pause: the calling thread sleeps."""

from __future__ import annotations

import time

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_waiter import (
    IBotWaiter,
)


class ThreadBotWaiter(IBotWaiter):
    def pause(self, seconds: float) -> None:
        time.sleep(seconds)
