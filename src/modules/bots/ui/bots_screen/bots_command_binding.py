"""How the Bots mode performs its commands (`EPIC-033D`): each lifecycle
command asks for its action on the selected bot, as its button did, and is
enabled by that action's rule (`bot_action_rules.py`) unless another action
is in flight. The commands themselves are declared Qt-free in
`bots_commands.py`.

A disabled button used to say why in its tooltip. `EPIC-033D` accepted losing
that reason because an action's tip is fixed by its declaration; `EPIC-034A`
reversed the trade-off: the binding sets the tip on the `QAction` itself, so
the menu, the toolbar and any shortcut hint carry the reason
(`ActionAvailability.reason`), and the Plan panel shows Start's on a line.
"""

from __future__ import annotations

from PySide6.QtGui import QAction
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
    lifecycle_id,
)
from .bots_view_model import BotsViewModel
from .kind_command_binding import KindCommands

NO_SELECTION_REASON = "Select a bot first."
ANOTHER_ACTION_REASON = "Another action is still running."


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
    command = lifecycle_id(action)
    binder.bind(
        command,
        lambda _checked: view_model.action_requested.emit(action.value),
        enabled=state.changed,
        initially_enabled=state.value,
    )
    _keep_tip_in_step(binder.action(command), view_model, action)


def _keep_tip_in_step(
    qaction: QAction, view_model: BotsViewModel, action: BotAction
) -> None:
    """The action's tip says what it does, and while it is disabled why not:
    `ActionAvailability.reason`, updated as the selection and the bot change."""
    declared = qaction.toolTip()

    def say() -> None:
        rule = view_model.availability.get(action)
        reason = rule.reason if rule is not None else NO_SELECTION_REASON
        if view_model.action_in_flight and rule is not None and rule.enabled:
            reason = ANOTHER_ACTION_REASON
        qaction.setToolTip(f"{declared}\n{reason}")

    view_model.actions_changed.connect(say)
    view_model.action_in_flight_changed.connect(say)
    say()
