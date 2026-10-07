"""How the Bots mode performs its commands (`EPIC-033D`): each lifecycle
command asks for its action on the selected bot, as its button did, and is
enabled by that action's rule (`bot_action_rules.py`) unless another action
is in flight. The commands themselves are declared Qt-free in
`bots_commands.py`.

A disabled button used to say why in its tooltip; an action's tooltip is
fixed by its declaration, so that reason is not shown on the action. The
Start refusal still reads in the Plan panel's verdicts. Recorded in
`EPIC-033D`'s notes.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState

from ..strategies.venue_strategies import VenueStrategies
from .bot_action_rules import BotAction
from .bots_commands import (
    ARM_STRATEGY,
    DISARM_STRATEGY,
    FIT_LEVELS,
    NEW_BOT,
    REFRESH_FILLS,
    RETRY_CONNECTION,
    lifecycle_id,
)
from .bots_view_model import BotsViewModel
from .kind_command_binding import KindCommands


def bind_bots_commands(
    binder: ICommandBinder, view_model: BotsViewModel, strategies: VenueStrategies
) -> None:
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
    # The levels are the selected bot's; with none selected nothing is drawn.
    chart = DerivedState(
        view_model.selection_changed,
        lambda: view_model.selected is not None,
        view_model,
    )
    binder.bind(
        FIT_LEVELS,
        lambda _checked: view_model.fit_levels_requested.emit(),
        enabled=chart.changed,
        initially_enabled=chart.value,
    )
    # `EPIC-034D`: a venue account that could not be read is read again.
    retry = DerivedState(
        view_model.connect_changed,
        lambda: view_model.connect_view.can_retry,
        view_model,
    )
    binder.bind(
        RETRY_CONNECTION,
        lambda _checked: view_model.retry_connect_requested.emit(),
        enabled=retry.changed,
        initially_enabled=retry.value,
    )
    for action in BotAction:
        _bind_lifecycle(binder, view_model, action)
    # The selected kind's own commands follow its toolbar; the presenter
    # hands each new editor over (`KindCommands.follow_panel_of`).
    KindCommands(view_model).bind_commands(binder)
    # The Strategies panel's selected venue (`EPIC-033K` stage 3).
    strategies.bind_commands(binder, ARM_STRATEGY, DISARM_STRATEGY)


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
