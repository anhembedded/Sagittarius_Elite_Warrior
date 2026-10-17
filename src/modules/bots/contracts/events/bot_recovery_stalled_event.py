"""`EPIC-042C` (ADR 042 D11) - a bot has waited to recover longer than it should expect to.

The wait has no limit (the owner chose to keep waiting and tell, not to give up), and a wait is
silent: entering the state is not an alert. This event is the one thing that makes a long wait
visible; `EPIC-042D` turns it into the `BOT_RECOVERY_STALLED` alert.
"""

from __future__ import annotations

from dataclasses import dataclass

from sagittarius_engine.domain.base_event import BaseEvent


@dataclass
class BotRecoveryStalledEvent(BaseEvent):
    """
    @brief Published once per wait, when the bot has been waiting for its halt's cause to clear
    for the rule's `stalled_after`. The bot goes on waiting and still recovers if the cause clears.

    @details Kind-neutral. Published from the bot's worker thread.
    """

    bot_id: str
    #: The halt reason it is waiting on (`GridReason.value`).
    reason: str
    #: How long it has waited, in whole seconds.
    waited_s: int
