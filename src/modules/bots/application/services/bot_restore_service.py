"""`EPIC-029B` — what a restart does to every saved bot (ADR D12).

Run once at boot. Each bot goes through `app_restart` in the lifecycle table:
RUNNING and PAUSED become RECOVERING, STARTING becomes HALTED (it may hold a
half-sliced opening buy), and every other state keeps itself. A changed bot is
saved, so the file says what the app now believes. Nothing is placed or
cancelled here (D12); reconciling a RECOVERING bot waits for the user to enable
trading on its venue (`EPIC-029E`).

A Grid restored from STARTING is saved with `START_INTERRUPTED` on its record
(`EPIC-035C`): its tagged orders are owed a cancel, and the debt is on the
bot's own file so that a second crash before it is paid does not lose it.
`BotBootRecovery` pays it at boot and the switch-on pays it again until done.

A refused file is logged by name and left untouched: rewriting a file this code
cannot read could destroy the only record of a bot that owns orders.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_interrupted_start import (
    START_INTERRUPTED_DETAIL,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    GridRuntimeCodecError,
    decode_runtime,
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    JsonValue,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
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
                self._store.save(StoredBot(restored, self._runtime_for(stored)))
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

    def _runtime_for(self, stored: StoredBot) -> Mapping[str, JsonValue]:
        """The runtime to save with the restored bot: as it was, except that a
        Grid cut off while STARTING records the cancel it is owed."""
        bot = stored.bot
        if (
            bot.state is not BotLifecycleState.STARTING
            or bot.definition.kind != GRID_KIND_ID
        ):
            return stored.runtime
        try:
            runtime = (
                decode_runtime(stored.runtime) if stored.runtime else GridRuntime(())
            )
        except GridRuntimeCodecError as exc:
            logger.error(
                "Bot %s was starting when the app closed and its runtime cannot "
                "be read (%s): orders from the interrupted start may rest",
                bot.bot_id,
                exc,
            )
            return stored.runtime
        return encode_runtime(
            runtime.with_reason(GridReason.START_INTERRUPTED, START_INTERRUPTED_DETAIL)
        )
