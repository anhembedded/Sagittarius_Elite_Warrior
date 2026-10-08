"""`EPIC-035C` (H6) — what the boot does for the bots a restart left unmanaged.

Run once at boot, after `BotRestoreService`. For every stored Grid:

  · **RECOVERING** → its executor reads the exchange and puts a
    `RecoveryReport` on the bot (`GridRecoveryReader`). Read-only; the full
    reconcile still waits for the order session.
  · **HALTED, owing a cancel** (`START_INTERRUPTED`: the restart cut its start
    short) → its executor cancels the bot's tagged orders when the exchange
    lets it (`GridInterruptedStart`).

Both run on the bot's own worker, so boot never waits on the network, and a
failed read is a report on the bot, not a failed boot. The switch-on event
repeats the cancel until it is paid, so a boot that could not pay it (the order
session is closed at boot) loses nothing.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_progress_reader import (
    bot_progress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.Restore")


class BotBootRecovery:
    """Starts the read and the cleanup each restored bot owes."""

    def __init__(self, store: IBotStore, executors: BotExecutors) -> None:
        self._store = store
        self._executors = executors

    def run(self) -> None:
        reported = cleaned = 0
        for stored in self._store.load_all().bots:
            bot = stored.bot
            if bot.state is BotLifecycleState.RECOVERING:
                reported += self._start(bot, lambda e: e.recover_after_restart())
            elif bot.state is BotLifecycleState.HALTED and _owes_a_cancel(stored):
                cleaned += self._start(bot, lambda e: e.recover_after_restart())
        logger.info(
            "[boot-recovery] %d recovering bot(s) read, %d interrupted start(s) cleaned",
            reported,
            cleaned,
        )

    def _start(self, bot: Bot, ask: Callable[[GridExecutor], None]) -> int:
        """Ask `bot`'s executor; 1 when asked. One bot whose executor cannot be
        built (a config the planner refuses) is logged and left as it is: it
        must not stop the others, or the app, from booting."""
        try:
            ask(self._executors.for_bot(bot))
        except Exception:
            logger.exception(
                "Bot %s: boot recovery skipped; the bot is left as restored",
                bot.bot_id,
            )
            return 0
        return 1


def _owes_a_cancel(stored: StoredBot) -> bool:
    progress = bot_progress(stored)
    return (
        progress is not None and progress.reason == GridReason.START_INTERRUPTED.value
    )
