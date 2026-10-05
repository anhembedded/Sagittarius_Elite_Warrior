"""How the Dev Board performs its commands (`EPIC-033D`): each to the
view-model request a header button used to make. The commands themselves are
declared Qt-free in `dev_board_commands.py`."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

from .dashboard_view_model import DashboardQmlViewModel
from .dev_board_commands import (
    EMERGENCY_STOP,
    ENABLE_TRADING,
    NEW_ORDER,
    RELOAD_HISTORY,
)


def bind_dev_board_commands(
    binder: ICommandBinder,
    view_model: DashboardQmlViewModel,
    open_new_order: Callable[[], None],
) -> None:
    """What `DashboardPresenter.bind_commands` binds, each enabled from the
    view model's state."""
    binder.bind(
        RELOAD_HISTORY,
        lambda _checked: view_model.requestLoadHistory(),
        enabled=view_model.reloadAvailable,
        initially_enabled=view_model.reload_is_available,
    )
    binder.bind(
        ENABLE_TRADING,
        lambda _checked: view_model.requestToggle(),
        enabled=view_model.toggleAvailable,
        checked=view_model.tradingEnabled,
    )
    binder.bind(EMERGENCY_STOP, lambda _checked: view_model.requestEmergencyStop())
    binder.bind(NEW_ORDER, lambda _checked: open_new_order())
