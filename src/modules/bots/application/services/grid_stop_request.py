"""`EPIC-035V` — whether the user pressed Stop while a start's orders were still being laid.

@details Shared by every opening strategy and by the ladder: a start that sees it lays nothing
more and leaves the bot STARTING for the Stop queued behind it to end (L9).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)

logger = logging.getLogger("App.Bots.GridExecutor")


def stop_asked(context: GridRunContext) -> bool:
    """The user pressed Stop while this start ran: it lays nothing more and
    leaves the bot STARTING for the Stop queued behind it to end
    (`EPIC-035V`, L9)."""
    if not context.stop_requested.is_set():
        return False
    logger.info(
        "Bot %s: Stop asked; the start lays no more orders", context.state.bot_id
    )
    return True
