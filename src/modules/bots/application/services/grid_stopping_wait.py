"""`EPIC-029E` — how a Grid's stop says what it waits for, shared by the sequence and its closers.

@details A stop that cannot finish stays STOPPING and writes the reason's detail with the
`WAITING` prefix; the prefix is cleared on STOPPED so the final state shows why the bot stopped,
not what it once waited for.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The prefix of a reason detail while STOPPING waits; cleared on STOPPED.
WAITING = "waiting:"


def wait_in_stopping(context: GridRunContext, detail: str) -> None:
    state = context.state
    reason = state.runtime.reason or GridReason.USER_STOP
    state.update(state.runtime.with_reason(reason, f"{WAITING} {detail}"))
    logger.info("Bot %s: STOPPING waits — %s", state.bot_id, detail)
