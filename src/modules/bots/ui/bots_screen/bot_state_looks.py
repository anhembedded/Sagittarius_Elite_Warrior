"""`EPIC-043C` — how a bot's lifecycle state is told: a word, an icon and a tone.

One table per thing the screen says about a state, each complete or the app does not start
(`EnumLabels`; the looks are checked by a test against every member). The word is what carries the
meaning, in the Bots table, the Plan dock and the identity strip; the icon and the colour of its tone
(`meaning_colours.py`) are beside it, never instead (`ui-presentation-rule.md` §1). A state that needs
the owner is a stop sign (a halt, an error); one that waits is a clock or a circle of arrows (paused,
recovering); one that runs is a play mark.

The word was `value.capitalize()`, which wrote `AWAITING_RECOVERY` as `Awaiting_recovery`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState as S,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_look import StateLook

STATE_WORDS = EnumLabels(
    S,
    {
        S.DRAFT: "Draft",
        S.STARTING: "Starting",
        S.RUNNING: "Running",
        S.PAUSED: "Paused",
        S.RECOVERING: "Recovering",
        S.HALTED: "Halted",
        S.AWAITING_RECOVERY: "Awaiting recovery",
        S.STOPPING: "Stopping",
        S.STOPPED: "Stopped",
        S.ERROR: "Error",
    },
)

#: A state with no entry is told by its word alone (a draft has not run).
STATE_LOOKS: dict[S, StateLook] = {
    S.STARTING: StateLook("clock", Tone.NEUTRAL),
    S.RUNNING: StateLook("play", Tone.POSITIVE),
    S.PAUSED: StateLook("pause", Tone.CAUTION),
    S.RECOVERING: StateLook("rotate-ccw", Tone.CAUTION),
    S.HALTED: StateLook("triangle-alert", Tone.NEGATIVE),
    S.AWAITING_RECOVERY: StateLook("rotate-ccw", Tone.CAUTION),
    S.STOPPING: StateLook("clock", Tone.NEUTRAL),
    S.STOPPED: StateLook("square", Tone.NEUTRAL),
    S.ERROR: StateLook("triangle-alert", Tone.NEGATIVE),
}


def state_text(state: S) -> str:
    """The state as the list and the header name it: `Running`, `Halted`."""
    return STATE_WORDS[state]


def state_look(state: S) -> StateLook | None:
    return STATE_LOOKS.get(state)


def state_tone(state: S) -> Tone:
    look = STATE_LOOKS.get(state)
    return Tone.NEUTRAL if look is None else look.tone
