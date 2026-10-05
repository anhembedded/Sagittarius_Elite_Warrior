"""How the Dev Board performs its commands (`EPIC-033D`): each to the
view-model request a header button used to make. The commands themselves are
declared Qt-free in `dev_board_commands.py`."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState

from .dashboard_view_model import DashboardQmlViewModel
from .dev_board_commands import (
    EMERGENCY_STOP,
    ENABLE_TRADING,
    LOAD_HISTORY,
    NEW_ORDER,
    START_LIVE,
    STOP_LIVE,
)

#: BOT-123: Start live spends its first phase in LOCKED, syncing from Binance
#: before the websocket opens, sometimes for many seconds. Stop live is how
#: the user cancels that sync (`StreamLifecycleController._on_stop_stream`
#: cancels the token the sync reads), so it applies in LOCKED as well as LIVE.
_STOPPABLE_MODES = frozenset({"LIVE", "LOCKED"})


def bind_dev_board_commands(
    binder: ICommandBinder,
    view_model: DashboardQmlViewModel,
    open_new_order: Callable[[], None],
) -> None:
    """What `DashboardPresenter.bind_commands` binds, each enabled from the
    view model's existing notifications."""
    loadable = DerivedState(
        view_model.uiModeChanged,
        lambda: bool(view_model.controlsEnabled) and not view_model.historyLoading,
        view_model,
    )
    loadable.listen(view_model.historyLoadingChanged)
    for command_id, request in (
        (LOAD_HISTORY, view_model.requestLoadHistory),
        (START_LIVE, view_model.requestStartStream),
    ):
        _bind(binder, command_id, request, loadable)
    stoppable = DerivedState(
        view_model.uiModeChanged,
        lambda: view_model.uiMode in _STOPPABLE_MODES,
        view_model,
    )
    _bind(binder, STOP_LIVE, view_model.requestStopStream, stoppable)
    toggle_available = DerivedState(
        view_model.tradingStateChanged, lambda: not view_model.toggleBusy, view_model
    )
    trading_on = DerivedState(
        view_model.tradingStateChanged, lambda: bool(view_model.enabled), view_model
    )
    binder.bind(
        ENABLE_TRADING,
        lambda _checked: view_model.requestToggle(),
        enabled=toggle_available.changed,
        checked=trading_on.changed,
        initially_enabled=toggle_available.value,
    )
    # The session's state was set before this binding existed.
    trading_on.announce()
    binder.bind(EMERGENCY_STOP, lambda _checked: view_model.requestEmergencyStop())
    binder.bind(NEW_ORDER, lambda _checked: open_new_order())


def _bind(
    binder: ICommandBinder,
    command_id: str,
    request: Callable[[], None],
    state: DerivedState,
) -> None:
    binder.bind(
        command_id,
        _ignoring_checked(request),
        enabled=state.changed,
        initially_enabled=state.value,
    )


def _ignoring_checked(request: Callable[[], None]) -> Callable[[bool], None]:
    def run(_checked: bool) -> None:
        request()

    return run
