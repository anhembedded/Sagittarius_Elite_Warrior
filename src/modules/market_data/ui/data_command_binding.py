"""How the Data mode performs its commands (`EPIC-033D`, `EPIC-033J`): each to
the view-model request its control used to make, enabled while what it acts
on is there and no task runs. The commands are declared Qt-free in
`data_commands.py`.

What a command acts on is the view's `selection` (the shard selected in the
coverage table, the gap selected in the Gaps panel); the two that ask first
(Sync history…, Import data…) put the answer in the view model's fields,
which the sync and import coordinators read.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.derived_state import DerivedState

from .data_commands import (
    CHECK_GAPS,
    DELETE_SELECTED,
    EXPORT,
    IMPORT,
    INSPECT_CANDLES,
    OPTIMIZE,
    PURGE_ALL,
    REPAIR_ALL_GAPS,
    REPAIR_GAP,
    SCAN_ALL,
    SCAN_STATUS,
    STOP,
    SYNC_ALL_GAPS,
    SYNC_HISTORY,
)
from .data_management_view_model import DataManagementViewModel
from .data_management_widgets.shard_dialogs import ShardChoice

if TYPE_CHECKING:
    from .data_management_view import DataManagementView

_IDLE_MODE = "IDLE"
#: A running task that Stop can still stop.
_STOPPABLE_MODES = frozenset({"SCANNING", "SYNCING", "CLEARING"})


class DataCommands:
    """The commands that need more than one view-model call.

    The view model's fields are Qt `Property`s, which mypy cannot read
    through (`EPIC-002D`); they are read and written by name, through the
    same setters an assignment calls."""

    def __init__(
        self, view_model: DataManagementViewModel, view: DataManagementView
    ) -> None:
        self._vm = view_model
        self._view = view

    def _text(self, name: str) -> str:
        return str(self._vm.property(name))

    def _texts(self, name: str) -> list[str]:
        return [str(value) for value in self._vm.property(name)]

    def _current(self) -> ShardChoice:
        return ShardChoice(self._text("selectedSymbol"), self._text("selectedInterval"))

    def _choose(self, shard: ShardChoice) -> None:
        self._vm.setProperty("selectedSymbol", shard.symbol)
        self._vm.setProperty("selectedInterval", shard.interval)

    def sync_history(self) -> None:
        """Asks which shard (the selected one, to start) and which range."""
        choice = self._view.ask_sync_history(
            self._texts("symbolOptions"), self._texts("intervals"), self._current()
        )
        if choice is None:
            return
        self._choose(choice.shard)
        self._vm.setProperty("useCustomTime", choice.start is not None)
        if choice.start is not None and choice.end is not None:
            self._vm.setProperty("fromDateTime", choice.start)
            self._vm.setProperty("toDateTime", choice.end)
        self._vm.requestSync()

    def import_data(self) -> None:
        """Asks which shard the file belongs to; the request asks the file."""
        choice = self._view.ask_import_shard(
            self._texts("symbolOptions"), self._texts("intervals"), self._current()
        )
        if choice is None:
            return
        self._choose(choice)
        self._vm.requestImport()

    def check_gaps(self) -> None:
        shard = self._view.selection.shard
        if shard is not None:
            self._vm.requestInspectGaps(shard.symbol, shard.interval)

    def inspect_candles(self) -> None:
        shard = self._view.selection.shard
        if shard is not None:
            self._vm.requestInspectKlines(shard.symbol, shard.interval)

    def repair_gap(self) -> None:
        gap = self._view.selection.gap
        report = self._view.gaps.report
        if gap is not None and report is not None:
            self._vm.requestRepairGap(
                report.symbol, report.interval, gap.fetch_start, gap.fetch_end
            )

    def repair_all_gaps(self) -> None:
        report = self._view.gaps.report
        if report is not None and report.gaps:
            self._vm.requestRepairAllGaps(report.symbol, report.interval)


def bind_data_commands(
    binder: ICommandBinder,
    view_model: DataManagementViewModel,
    view: DataManagementView,
) -> DataCommands:
    """What `DataManagementPresenter.bind_commands` binds; returns the object
    the handlers live on, for the presenter to keep."""
    commands = DataCommands(view_model, view)
    selection = view.selection

    def idle() -> bool:
        return view_model.uiMode == _IDLE_MODE

    def state(read: Callable[[], bool]) -> DerivedState:
        derived = DerivedState(view_model.uiModeChanged, read, view_model)
        derived.listen(selection.changed)
        return derived

    shard = state(lambda: idle() and selection.shard is not None)
    unhealthy = state(
        lambda: (
            idle() and selection.shard is not None and not selection.shard.is_healthy
        )
    )
    gap = state(lambda: idle() and selection.gap is not None)
    gaps = state(lambda: idle() and selection.gaps_listed)
    running = state(lambda: view_model.uiMode in _STOPPABLE_MODES)
    free = state(idle)
    bindings: dict[str, tuple[Callable[[], None], DerivedState]] = {
        SYNC_HISTORY: (commands.sync_history, free),
        CHECK_GAPS: (commands.check_gaps, unhealthy),
        REPAIR_GAP: (commands.repair_gap, gap),
        REPAIR_ALL_GAPS: (commands.repair_all_gaps, gaps),
        INSPECT_CANDLES: (commands.inspect_candles, shard),
        STOP: (view_model.requestCancel, running),
        SCAN_STATUS: (view_model.requestCheckStatus, shard),
        SCAN_ALL: (view_model.requestCheckAllStatus, free),
        SYNC_ALL_GAPS: (view_model.requestSyncAllGaps, free),
        EXPORT: (view_model.requestExport, shard),
        IMPORT: (commands.import_data, free),
        OPTIMIZE: (view_model.requestVacuum, free),
        DELETE_SELECTED: (view_model.requestClearData, shard),
        PURGE_ALL: (view_model.requestPurgeAll, free),
    }
    for command_id, (request, enabled) in bindings.items():
        binder.bind(
            command_id,
            _ignoring_checked(request),
            enabled=enabled.changed,
            initially_enabled=enabled.value,
        )
    return commands


def _ignoring_checked(request: Callable[[], None]) -> Callable[[bool], None]:
    def run(_checked: bool) -> None:
        request()

    return run
