"""`EPIC-035G`, owner decision D6 — a store that keeps failing pauses the bot.

`BotRunState` keeps a failed write as a fact so a bot can still park its ladder.
It must not keep *trading* on memory for good: after `FAILED_SAVES_BEFORE_PAUSE`
writes in a row fail (a success resets the count) a RUNNING bot goes to PAUSED
with `STORAGE_FAILURE` and the failure on its detail. A pause is what it always
is: the resting orders stay on the exchange, the counter orders a fill owes are
held, and nothing new is placed.

Only the user's Resume ends it, and only once the store takes a write: `admits_resume`
writes the record once and, when that fails, leaves the bot PAUSED (the failed write
is already logged `[bot-store-failed]`). A resume that went on regardless would
release the held orders into a bot whose file cannot say it is running.

The check runs after each worker task (`GridTaskGuard`), so a task that is already
under way finishes its own placements; the pause bites from the next one.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: Consecutive failed writes that pause a running bot (owner decision D6).
FAILED_SAVES_BEFORE_PAUSE = 3


class GridStorageWatch:
    """Pauses a bot whose store keeps failing, and gates its way back."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def pause_if_failing(self) -> None:
        """Pause a RUNNING bot once its writes have failed three times in a row."""
        state = self._context.state
        if (
            state.state is not BotLifecycleState.RUNNING
            or state.failed_saves < FAILED_SAVES_BEFORE_PAUSE
        ):
            return
        detail = (
            f"{state.failed_saves} saves in a row failed ({state.storage_failure}); "
            "its orders rest on the exchange and nothing new is placed. "
            "Resume once the disk accepts a write"
        )
        logger.error("Bot %s: %s [bot-store-failed-paused]", state.bot_id, detail)
        state.transition(BotLifecycleEvent.PAUSE, GridReason.STORAGE_FAILURE, detail)

    def admits_resume(self) -> bool:
        """Whether a PAUSED bot may resume now: unless it is paused for its
        storage, always; if so, only when the store takes a write."""
        state = self._context.state
        if state.runtime.reason is not GridReason.STORAGE_FAILURE:
            return True
        if not state.save_works():
            logger.warning(
                "Bot %s: resume refused, its state still cannot be saved (%s) "
                "[bot-store-failed]",
                state.bot_id,
                state.storage_failure,
            )
            return False
        state.update(replace(state.runtime, reason=None, reason_detail=""))
        return True
