"""QML-facing wrapper around the real `DatabaseStatusTableModel`.

EPIC-015 Phase 2 (2026-08-30): search, row actions, and the idle/busy
toggle are real now. The earlier "structural pass only" era this module's
`NOTES.md` used to describe — `rowActionRequested` with no wiring, no
search box — is over; see `NOTES.md` for the up-to-date picture.

This VM owns its own `DatabaseStatusFilterProxy` (same class
`database_status_table_model.py` already defined for exactly this) rather
than requiring a host to hand it an already-filtered model. That keeps the
widget self-contained: any host constructs it from the one raw
`DatabaseStatusTableModel`, and the widget does its own filtering —
consistent with `qml-rule.md` §1.2 ("the widget VM holds the whole rule",
not half of it split across the widget and its host).
"""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.database_status_table_model import (
    DatabaseStatusFilterProxy,
    DatabaseStatusTableModel,
)


class DatabaseStatusVM(QObject):
    rowCountChanged = Signal()
    actionsEnabledChanged = Signal()
    rowActionRequested = Signal(str, str, str)  # action, symbol, interval

    def __init__(
        self,
        model: DatabaseStatusTableModel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_model = model
        self._proxy = DatabaseStatusFilterProxy(self)
        self._proxy.setSourceModel(model)
        self._actions_enabled = True
        # The proxy's own row count (what QML and the badge actually show)
        # changes whenever the source model does — `set_search_text()`
        # re-filtering is handled separately in `setSearchText()` below,
        # since `invalidateFilter()` emits no signal this VM can forward.
        self._source_model.countsChanged.connect(self.rowCountChanged)

    @Property(QObject, constant=True)
    def rowsModel(self) -> DatabaseStatusFilterProxy:
        """The search-filtered view of the table — QML binds
        `model: vm.rowsModel`. `QSortFilterProxyModel` passes the source
        model's roles straight through, so a row's fields still come from
        `DatabaseStatusTableModel` directly, not a second copy of the
        data."""
        return self._proxy

    @Property(int, notify=rowCountChanged)
    def rowCount(self) -> int:
        """The count actually visible right now — filtered, if a search is
        active. Drives both the header badge and the empty-state message,
        matching the old `_StatusRowWidget` screen's `model.rowCount()`,
        which read the same filtered proxy."""
        return self._proxy.rowCount()

    @Slot(str)
    def setSearchText(self, text: str) -> None:
        """Forwards to the internal proxy. `invalidateFilter()` (inside
        `set_search_text()`) emits Qt's own layout signals, not
        `countsChanged` — that signal lives on the source model and reports
        the *unfiltered* count — so `rowCountChanged` is emitted here
        directly whenever filtering actually changed what is visible."""
        before = self._proxy.rowCount()
        self._proxy.set_search_text(text)
        if self._proxy.rowCount() != before:
            self.rowCountChanged.emit()

    @Property(bool, notify=actionsEnabledChanged)
    def actionsEnabled(self) -> bool:
        return self._actions_enabled

    @Slot(bool)
    def setActionsEnabled(self, enabled: bool) -> None:
        """Mirrors `_StatusRowWidget.apply_ui_mode(idle)`'s exact rule:
        while not idle, every row's four action buttons are disabled. A
        host calls this from its own `uiMode` sync — the same trigger the
        old widget used."""
        if enabled == self._actions_enabled:
            return
        self._actions_enabled = enabled
        self.actionsEnabledChanged.emit()

    @Slot(str, str, str)
    def requestAction(self, action: str, symbol: str, interval: str) -> None:
        self.rowActionRequested.emit(action, symbol, interval)
