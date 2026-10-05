"""How the Bots mode performs its commands (`EPIC-033D`): each lifecycle
command asks for its action on the selected bot, as its button did, and is
enabled by that action's rule (`bot_action_rules.py`) unless another action
is in flight. The commands themselves are declared Qt-free in
`bots_commands.py`.

A disabled button used to say why in its tooltip; an action's tooltip is
fixed by its declaration, so that reason is not shown on the action. The
Start refusal still reads in the Parameters tab's verdicts. Recorded in
`EPIC-033D`'s notes.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState

from .bot_action_rules import BotAction
from .bots_commands import NEW_BOT, REFRESH_FILLS, lifecycle_id
from .bots_view_model import BotsViewModel


def bind_bots_commands(binder: ICommandBinder, view_model: BotsViewModel) -> None:
    """What `BotsPresenter.bind_commands` binds."""
    idle = DerivedState(
        view_model.action_in_flight_changed,
        lambda: not view_model.action_in_flight,
        view_model,
    )
    binder.bind(
        NEW_BOT,
        lambda _checked: view_model.new_bot_requested.emit(),
        enabled=idle.changed,
        initially_enabled=idle.value,
    )
    # The fills belong to the selected bot: with none selected the read has
    # nothing to fetch, so the command waits for a selection, as it did in
    # the selected bot's Fills tab.
    fills = DerivedState(
        view_model.selection_changed,
        lambda: view_model.selected is not None and not view_model.action_in_flight,
        view_model,
    )
    fills.listen(view_model.action_in_flight_changed)
    binder.bind(
        REFRESH_FILLS,
        lambda _checked: view_model.refresh_fills_requested.emit(),
        enabled=fills.changed,
        initially_enabled=fills.value,
    )
    for action in BotAction:
        _bind_lifecycle(binder, view_model, action)


def _bind_lifecycle(
    binder: ICommandBinder, view_model: BotsViewModel, action: BotAction
) -> None:
    def applies() -> bool:
        rule = view_model.availability.get(action)
        return rule is not None and rule.enabled and not view_model.action_in_flight

    state = DerivedState(view_model.actions_changed, applies, view_model)
    state.listen(view_model.action_in_flight_changed)
    binder.bind(
        lifecycle_id(action),
        lambda _checked: view_model.action_requested.emit(action.value),
        enabled=state.changed,
        initially_enabled=state.value,
    )
