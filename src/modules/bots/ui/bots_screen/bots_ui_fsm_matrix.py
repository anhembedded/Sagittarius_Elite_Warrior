"""`EPIC-029F` — the Bots screen's own modes, apart from any bot's lifecycle.

Four modes: nothing selected, a bot being viewed, a bot being edited (its
parameters are editable where the lifecycle table declares `edit`: a DRAFT
or a STOPPED bot), and one action in flight. While
an action runs the list and every action are locked, so a second click can
never race the first (`async-ui-action-rule.md` §1); the action settles back
on whatever the selection then is, which may have changed state meanwhile.

A bot's own legal actions are its lifecycle table's (`bot_action_rules.py`);
this table only says what the screen is doing.
"""

from __future__ import annotations

from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_snapshot import (
    BotSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    is_declared,
)


class BotsUiState(str, Enum):
    NO_SELECTION = "NO_SELECTION"
    VIEWING = "VIEWING"
    EDITING_DRAFT = "EDITING_DRAFT"
    ACTION_IN_FLIGHT = "ACTION_IN_FLIGHT"


class BotsUiEvent(str, Enum):
    SELECTED_NONE = "SELECTED_NONE"
    SELECTED_BOT = "SELECTED_BOT"
    SELECTED_DRAFT = "SELECTED_DRAFT"
    ACTION_STARTED = "ACTION_STARTED"
    SETTLED_NONE = "SETTLED_NONE"
    SETTLED_BOT = "SETTLED_BOT"
    SETTLED_DRAFT = "SETTLED_DRAFT"


_AT_REST = (
    BotsUiState.NO_SELECTION,
    BotsUiState.VIEWING,
    BotsUiState.EDITING_DRAFT,
)

_SELECTED = {
    BotsUiEvent.SELECTED_NONE: BotsUiState.NO_SELECTION,
    BotsUiEvent.SELECTED_BOT: BotsUiState.VIEWING,
    BotsUiEvent.SELECTED_DRAFT: BotsUiState.EDITING_DRAFT,
}

_SETTLED = {
    BotsUiEvent.SETTLED_NONE: BotsUiState.NO_SELECTION,
    BotsUiEvent.SETTLED_BOT: BotsUiState.VIEWING,
    BotsUiEvent.SETTLED_DRAFT: BotsUiState.EDITING_DRAFT,
}

BOTS_UI_TRANSITIONS: dict[tuple[BotsUiState, BotsUiEvent], BotsUiState] = {
    **{
        (state, event): target
        for state in _AT_REST
        for event, target in _SELECTED.items()
    },
    **{
        (state, BotsUiEvent.ACTION_STARTED): BotsUiState.ACTION_IN_FLIGHT
        for state in _AT_REST
    },
    **{
        (BotsUiState.ACTION_IN_FLIGHT, event): target
        for event, target in _SETTLED.items()
    },
}


def selection_event(snapshot: BotSnapshot | None) -> BotsUiEvent:
    """What selecting `snapshot` (or nothing) dispatches."""
    if snapshot is None:
        return BotsUiEvent.SELECTED_NONE
    if is_declared(snapshot.state, BotLifecycleEvent.EDIT):
        return BotsUiEvent.SELECTED_DRAFT
    return BotsUiEvent.SELECTED_BOT


def settled_event(snapshot: BotSnapshot | None) -> BotsUiEvent:
    """What an action's end dispatches, given the selection it ends on."""
    return {
        BotsUiEvent.SELECTED_NONE: BotsUiEvent.SETTLED_NONE,
        BotsUiEvent.SELECTED_BOT: BotsUiEvent.SETTLED_BOT,
        BotsUiEvent.SELECTED_DRAFT: BotsUiEvent.SETTLED_DRAFT,
    }[selection_event(snapshot)]
