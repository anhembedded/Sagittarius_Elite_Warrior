"""`BUG-202` — what the status bar says when a bot command was accepted.

@details Accepted means the command was queued to the bot's own worker, not that it
worked. A resume from HALTED proposes a ladder (its log shows it) or stays HALTED
saying why (its Plan shows it); a confirmation lays the ladder or stays HALTED saying
why. Neither is "done" when the command returns, so those say what was sent and where
the outcome shows. A PAUSED bot's resume proposes nothing and keeps "done", as does
every other action.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bot_action_rules import (
    BotAction,
)

_PROPOSED = (
    "sent to the bot. Its log shows the proposed ladder to confirm; "
    "its Plan shows why it still waits."
)
_CONFIRMED = (
    "sent to the bot. It is RUNNING once the ladder is laid; "
    "otherwise its Plan shows why it stays HALTED."
)


def accepted_words(
    label: str, action: BotAction | None, state: BotLifecycleState | None
) -> str:
    """The status line for `label`, accepted, for a bot that was in `state`."""
    if action is BotAction.RESUME and state in RESUME_PROPOSES_STATES:
        return f"{label}: {_PROPOSED}"
    if action is BotAction.CONFIRM_RESUME:
        return f"{label}: {_CONFIRMED}"
    return f"{label}: done."
