"""How the Data mode performs its commands (`EPIC-033D`): each to the
view-model request its button used to make, all available while the mode is
idle. The commands themselves are declared Qt-free in `data_commands.py`."""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState

from .data_commands import (
    DELETE_SELECTED,
    EXPORT,
    IMPORT,
    OPTIMIZE,
    PURGE_ALL,
    SCAN_ALL,
    SCAN_STATUS,
    SYNC_ALL_GAPS,
    SYNC_TIMEFRAME,
)
from .data_management_view_model import DataManagementViewModel

_IDLE_MODE = "IDLE"


def bind_data_commands(
    binder: ICommandBinder, view_model: DataManagementViewModel
) -> None:
    """What `DataManagementPresenter.bind_commands` binds."""
    idle = DerivedState(
        view_model.uiModeChanged, lambda: view_model.uiMode == _IDLE_MODE, view_model
    )
    requests: dict[str, Callable[[], None]] = {
        SCAN_STATUS: view_model.requestCheckStatus,
        SCAN_ALL: view_model.requestCheckAllStatus,
        SYNC_TIMEFRAME: view_model.requestSync,
        SYNC_ALL_GAPS: view_model.requestSyncAllGaps,
        EXPORT: view_model.requestExport,
        IMPORT: view_model.requestImport,
        OPTIMIZE: view_model.requestVacuum,
        DELETE_SELECTED: view_model.requestClearData,
        PURGE_ALL: view_model.requestPurgeAll,
    }
    for command_id, request in requests.items():
        binder.bind(
            command_id,
            _ignoring_checked(request),
            enabled=idle.changed,
            initially_enabled=idle.value,
        )


def _ignoring_checked(request: Callable[[], None]) -> Callable[[bool], None]:
    def run(_checked: bool) -> None:
        request()

    return run
