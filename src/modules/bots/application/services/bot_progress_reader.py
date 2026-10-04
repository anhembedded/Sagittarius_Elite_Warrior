"""`EPIC-029F` — a stored bot's run account, read from the runtime its kind saved.

The runtime is opaque to everything but the kind (`StoredBot.runtime`), so the
reading lives with the kind's codec. Only Grid keeps one today.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_runtime_codec import (
    GridRuntimeCodecError,
    decode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_progress import (
    BotProgress,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import StoredBot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_KIND_ID,
)

logger = logging.getLogger("App.Bots.Progress")


def bot_progress(stored: StoredBot) -> BotProgress | None:
    """The run's account, or `None` when the bot has none yet (a draft, a
    kind with no runtime) or its runtime cannot be read."""
    if stored.bot.definition.kind != GRID_KIND_ID or not stored.runtime:
        return None
    try:
        runtime = decode_runtime(stored.runtime)
    except GridRuntimeCodecError as exc:
        logger.warning(
            "[bot-progress] bot %s: its runtime cannot be read (%s); no progress shown",
            stored.bot.bot_id.value,
            exc,
        )
        return None
    return BotProgress(
        realised_profit=runtime.realised_profit,
        completed_cycles=runtime.completed_cycles,
        open_orders=len(runtime.open_orders),
        inventory=runtime.inventory,
        average_cost=runtime.average_cost,
        reason=runtime.reason.value if runtime.reason is not None else "",
        reason_detail=runtime.reason_detail,
    )
