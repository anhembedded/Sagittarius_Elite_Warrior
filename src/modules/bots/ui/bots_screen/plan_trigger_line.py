"""`EPIC-046B` (ADR 046 D3, D5) - the plan's trigger line is drawn only while it can still hold an entry.

The overlay is the plan's (`grid_overlay`), so it always carries the trigger line. Once the bot
has laid its ladder the trigger is never asked again, as a filled limit order is not redrawn: the
Bots screen leaves the line out for a bot whose state holds a laid ladder, and for a RECOVERING
bot that returns to one. A bot at rest, waiting, halted or in error keeps the line, because its
next Start, or a Resume of it while it holds nothing, asks the trigger again.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_overlay import (
    BotOverlay,
    OverlayRole,
)

_S = BotLifecycleState

#: The states in which the bot has laid, is laying or is taking down its ladder.
TRIGGER_LATCHED_STATES: frozenset[BotLifecycleState] = frozenset(
    {_S.STARTING, _S.RUNNING, _S.PAUSED, _S.STOPPING}
)


def trigger_latched(bot: BotSnapshot) -> bool:
    if bot.state is _S.RECOVERING:
        return bot.recovering_from in TRIGGER_LATCHED_STATES
    return bot.state in TRIGGER_LATCHED_STATES


def shown_for(overlay: BotOverlay | None, bot: BotSnapshot) -> BotOverlay | None:
    """`overlay` as the screen draws it for `bot`: without the trigger line once it latched."""
    if overlay is None or not trigger_latched(bot):
        return overlay
    return replace(
        overlay,
        lines=tuple(
            line for line in overlay.lines if line.role is not OverlayRole.TRIGGER
        ),
    )
