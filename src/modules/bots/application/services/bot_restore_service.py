"""`EPIC-029B` — what a restart does to every saved bot (ADR D12).

Run once at boot. Each bot goes through `app_restart` in the lifecycle table:
RUNNING and PAUSED become RECOVERING, STARTING becomes HALTED (it may hold a
half-sliced opening buy), and every other state keeps itself. A changed bot is
saved, so the file says what the app now believes. Nothing is placed or
cancelled here (D12); reconciling a RECOVERING bot waits for the user to enable
trading on its venue (`EPIC-029E`).

A refused file is logged by name and left untouched: rewriting a file this code
cannot read could destroy the only record of a bot that owns orders.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)

logger = logging.getLogger("App.Bots.Restore")


class BotRestoreService:
    """Applies the restart rule to every stored bot."""

    def __init__(self, store: IBotStore, clock: IBotClock) -> None:
        self._store = store
        self._clock = clock

    def restore_all(self) -> None:
        reading = self._store.load_all()
        now = self._clock.now()
        for stored in reading.bots:
            restored = stored.bot.restored(now)
            if restored != stored.bot:
                self._store.save(StoredBot(restored, stored.runtime))
                logger.info(
                    "Restored bot %s: %s -> %s",
                    restored.bot_id,
                    stored.bot.state.value,
                    restored.state.value,
                )
        for refused in reading.refused:
            logger.error(
                "Bot file %s was not restored: %s", refused.name, refused.reason
            )
