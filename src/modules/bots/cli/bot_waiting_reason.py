"""`EPIC-044C` - what `bot list` and `bot show` print as the reason of a bot waiting for its range.

A list has no column for the range and the price a waiting bot waits on, so they take the reason's
place (`bot show` repeats them under Reason and has the ladder's rows below). A bot that has a
reason of its own keeps it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_status_report import (
    BotStatusEntry,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder import GridLadder
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.grid_ladder_texts import (
    waiting_text,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.run_earnings import (
    plain_price,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)


def reason_cell(bot: BotStatusEntry) -> str:
    """Why the bot is as it is; for a bot waiting for its range, the range and the price
    (`EPIC-044C`), which a list has no other column for."""
    waiting = _waiting_text(bot)
    return bot.reason if waiting is None or bot.reason else waiting


def _waiting_text(bot: BotStatusEntry) -> str | None:
    ladder = bot.ladder
    if bot.state != BotLifecycleState.AWAITING_RANGE.value or not isinstance(
        ladder, GridLadder
    ):
        return None
    return waiting_text(ladder.position, plain_price)
