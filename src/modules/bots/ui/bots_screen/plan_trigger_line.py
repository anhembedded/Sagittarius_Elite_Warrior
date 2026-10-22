"""`EPIC-046B` (ADR 046 D3, D5) - the plan's trigger line is drawn only while it can still hold an entry.

The overlay is the plan's (`grid_overlay`), so it always carries the trigger line. Once the bot
has laid its ladder the trigger is never asked again, as a filled limit order is not redrawn: the
Bots screen leaves the line out for a bot whose state holds a laid ladder, and for a RECOVERING
bot that returns to one. A halted bot, one awaiting recovery or one in error is judged by its
record: while it holds inventory or a position its Resume plans over what it holds and never asks
the trigger, so the line goes (review of #725); while it holds none the Resume cancels any
resting order, finds the bot flat and asks the trigger (`GridResumeSequence._wait_if_still_flat`),
so the line stays. A bot at rest or waiting keeps the line.
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


#: The states whose Resume asks the trigger only when the record holds nothing (ADR 046 D3).
RESUMED_BY_WHAT_IT_HOLDS: frozenset[BotLifecycleState] = frozenset(
    {_S.HALTED, _S.AWAITING_RECOVERY, _S.ERROR}
)


def trigger_latched(bot: BotSnapshot) -> bool:
    if bot.state is _S.RECOVERING:
        return bot.recovering_from in TRIGGER_LATCHED_STATES
    if bot.state in RESUMED_BY_WHAT_IT_HOLDS:
        return _holds_something(bot)
    return bot.state in TRIGGER_LATCHED_STATES


def _holds_something(bot: BotSnapshot) -> bool:
    progress = bot.progress
    return progress is not None and progress.inventory != 0


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
