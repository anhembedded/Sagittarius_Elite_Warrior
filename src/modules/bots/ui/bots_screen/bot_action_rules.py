"""`EPIC-029F` — which of a bot's buttons are live, and why the others are not.

Read from the lifecycle table (`is_declared`), never from a copy: a button is
enabled exactly when the use case behind it would accept the command. A
disabled button says why in its tooltip, so the reason is never colour alone
(`ui-presentation-rule.md`).

Start has three more conditions than the table, all shown before the click
rather than refused after it: the venue's account was read and its key may
trade (`EPIC-034D`), the kind's verdict (a REFUSED verdict names itself) and
unsaved edits (a start runs the saved parameters, so the edits are saved
first).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
    is_declared,
)


class BotAction(str, Enum):
    START = "Start"
    PAUSE = "Pause"
    RESUME = "Resume"
    CONFIRM_RESUME = "Confirm resume"
    STOP = "Stop"
    SAVE = "Save"
    DELETE = "Delete"


_EVENT = {
    BotAction.START: BotLifecycleEvent.START,
    BotAction.PAUSE: BotLifecycleEvent.PAUSE,
    BotAction.RESUME: BotLifecycleEvent.RESUME,
    BotAction.STOP: BotLifecycleEvent.STOP,
    BotAction.SAVE: BotLifecycleEvent.EDIT,
    BotAction.DELETE: BotLifecycleEvent.DELETE,
}


@dataclass(frozen=True, slots=True)
class ActionAvailability:
    enabled: bool
    #: Why it is disabled, or what it does when enabled; the tooltip.
    reason: str


@dataclass(frozen=True, slots=True)
class StartConditions:
    """What Start needs beyond the lifecycle table."""

    #: The kind's REFUSED verdict, or the reason none could be judged; empty
    #: when the plan may start.
    refusal: str = ""
    unsaved_edits: bool = False
    #: Why the bot's venue account has not been read, or may not trade
    #: (`EPIC-034D`); empty when it says go.
    connection: str = ""


def availability(
    state: BotLifecycleState,
    action: BotAction,
    start: StartConditions = StartConditions(),  # noqa: B008 -- frozen, no shared mutable state
) -> ActionAvailability:
    if action is BotAction.CONFIRM_RESUME:
        return _confirm_resume(state)
    if not is_declared(state, _EVENT[action]):
        return ActionAvailability(
            False, f"{action.value} is not possible while the bot is {_name(state)}."
        )
    if action is BotAction.START:
        if start.connection:
            return ActionAvailability(False, start.connection)
        if start.unsaved_edits:
            return ActionAvailability(False, "Save the changed parameters first.")
        if start.refusal:
            return ActionAvailability(False, start.refusal)
    return ActionAvailability(True, _WHAT_IT_DOES[action])


def _confirm_resume(state: BotLifecycleState) -> ActionAvailability:
    if state is not BotLifecycleState.HALTED:
        return ActionAvailability(
            False, f"Only a halted bot has a resume to confirm; it is {_name(state)}."
        )
    return ActionAvailability(True, _WHAT_IT_DOES[BotAction.CONFIRM_RESUME])


def _name(state: BotLifecycleState) -> str:
    return state.value.lower()


_WHAT_IT_DOES = {
    BotAction.START: "Place the ladder on the exchange.",
    BotAction.PAUSE: "Stop placing new orders; resting orders stay.",
    BotAction.RESUME: (
        "Resume. A halted bot first cancels its tagged orders and proposes a "
        "new ladder (shown in its log) for you to confirm."
    ),
    BotAction.CONFIRM_RESUME: "Lay the ladder the last Resume proposed.",
    BotAction.STOP: "Cancel the resting orders and stop; asks what to do with the base.",
    BotAction.SAVE: "Save the changed parameters.",
    BotAction.DELETE: "Delete this bot's definition.",
}
