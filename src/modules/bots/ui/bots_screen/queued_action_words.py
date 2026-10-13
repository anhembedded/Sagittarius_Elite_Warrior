"""`BUG-202` — what the status bar says when a bot command was accepted.

@details Accepted means the command was queued to the bot's own worker, not that it
worked. A resume from HALTED proposes a ladder, or stays HALTED saying why; a
confirmation lays the ladder, or stays HALTED saying why. Neither is "done" when the
command returns, so those two say what was sent and where the outcome shows. Every
other action keeps "done".
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)

_OUTCOME_SHOWS_ON_THE_BOT = {
    BotAction.RESUME: (
        "sent to the bot. Its Plan shows the proposed ladder to confirm, "
        "or why it still waits."
    ),
    BotAction.CONFIRM_RESUME: (
        "sent to the bot. It is RUNNING once the ladder is laid; "
        "otherwise its Plan shows why it stays HALTED."
    ),
}


def accepted_words(label: str, action: BotAction | None) -> str:
    """The status line for `label`, accepted."""
    queued = _OUTCOME_SHOWS_ON_THE_BOT.get(action) if action is not None else None
    return f"{label}: {queued}" if queued is not None else f"{label}: done."
