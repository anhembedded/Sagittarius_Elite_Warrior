from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot


@dataclass(frozen=True)
class _ScriptRow:
    key: str
    title: str


class IndicatorScriptListModel(QAbstractListModel):
    """
    @brief Backs the "CUSTOM SCRIPTS" checklist shared by Dashboard's and
    Backtest's indicator pickers — which registered indicator scripts
    exist, and which ones the user has enabled.

    @details
    The list of available scripts comes from IndicatorScriptRegistry.available()
    at runtime, so new scripts appear here automatically as soon as they're
    registered in binance_bot_module.py, with no view change needed.

    Enabled state lives here, in the ViewModel layer, not in the presenter.
    A presenter only reads `enabled_keys` at the moment Load History/Start
    Live is clicked — ticking a box mid-run has no retroactive effect
    (TC-GAP-07).

    Moved here from `screens/dashboard/` by `BOT-120` — Backtest's own
    ViewModel constructs one too, and nothing about "which indicator
    scripts are enabled" is specific to either screen. The docstring above
    used to name `DevBoardPanel.qml` and a QML `Repeater` delegate; both
    were dropped by `EPIC-006` and the mention was stale.
    """

    KeyRole = Qt.ItemDataRole.UserRole + 1
    TitleRole = Qt.ItemDataRole.UserRole + 2
    EnabledRole = Qt.ItemDataRole.UserRole + 3

    _ROLE_NAMES: ClassVar[dict[int, bytes]] = {
        KeyRole: b"key",
        TitleRole: b"title",
        EnabledRole: b"enabled",
    }

    enabledKeysChanged = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[_ScriptRow] = []
        self._enabled: set[str] = set()
        #: Keys the user has explicitly toggled by hand — set_available()
        #: only auto-enables a `default_enabled` script the FIRST time it's
        #: seen, never re-applying that default over a choice the user
        #: already made (e.g. after they turned a default-on script off).
        self._user_touched: set[str] = set()

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        parent_index = QModelIndex() if parent is None else parent
        return 0 if parent_index.isValid() else len(self._rows)

    def roleNames(self) -> dict:
        return dict(self._ROLE_NAMES)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None

        row = self._rows[index.row()]
        if role == self.KeyRole:
            return row.key
        if role == self.TitleRole:
            return row.title
        if role == self.EnabledRole:
            return row.key in self._enabled
        return None

    def set_available(self, scripts: Mapping[str, type]) -> None:
        """
        @brief Replaces the selectable script list, e.g. from
        IndicatorScriptRegistry.available().
        @details A key that stays available keeps its enabled state; a key
        that disappears (script unregistered) is dropped from `_enabled` too
        — otherwise a stale key could leak into enabled_keys forever. A key
        with `default_enabled = True` that the user has never manually
        touched is switched on — see `_user_touched`.
        """
        self.beginResetModel()
        self._rows = [
            _ScriptRow(key=key, title=getattr(cls, "title", key))
            for key, cls in scripts.items()
        ]
        self._enabled &= {row.key for row in self._rows}
        for key, cls in scripts.items():
            if getattr(cls, "default_enabled", False) and key not in self._user_touched:
                self._enabled.add(key)
        self.endResetModel()
        self.enabledKeysChanged.emit()

    @Slot(int, bool)
    def setEnabled(self, row: int, value: bool) -> None:
        """Called directly by each screen's checklist checkbox
        (`dev_board_panel.py`, `backtest_modals.py`) — kept as a `@Slot`
        from the QML-hosted era this class predates, not because anything
        still calls it across a QML/Python boundary."""
        if not 0 <= row < len(self._rows):
            return
        key = self._rows[row].key
        self._user_touched.add(key)
        if value:
            self._enabled.add(key)
        else:
            self._enabled.discard(key)
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, [self.EnabledRole])
        self.enabledKeysChanged.emit()

    @property
    def enabled_keys(self) -> list[str]:
        """Read by the Presenter at Load History/Start Live click time —
        order matches registration order, not click order."""
        return [row.key for row in self._rows if row.key in self._enabled]
