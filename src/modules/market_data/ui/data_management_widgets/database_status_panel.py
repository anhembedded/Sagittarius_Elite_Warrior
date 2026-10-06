"""The Database Status panel — a `QTableView` over the shards on disk; the
Data mode's central widget (`EPIC-033J`).

**The Data mode (`EPIC-033J`).** The toolbar above the table is gone: the
commands that act on the selected shard are the Data menu's (Check gaps,
Inspect candles, Delete data), and the panel reports the selection
(`shardSelected`) for them to act on. The table's context menu repeats them,
as context menus repeat menu commands (`ui-presentation-rule.md` §6). Syncing
a shard is Data → Sync history…, which opens on the selected shard.

**What this replaces.** `DatabaseStatusTable.qml` + `DatabaseStatusRow.qml`, a
hand-drawn table whose every row carried four `Button`s. That shape came from
QML, where a delegate is the only way to put a control in a row; on the desktop
it is the pattern ADR D20 rules out — a hand-drawn substitute for a component
the platform already has.

**So the actions moved out of the rows.** One `QAction` per user action, each
appearing in the toolbar above the table *and* in the row's context menu, and
each operating on the selected row — which is the Consistency principle's
"một `QAction` cho mỗi hành động" made literal, and the Efficiency principle's
keyboard path: `Tab` to the table, arrow to the shard, `Enter`-equivalent
double-click or the context menu. Four buttons × N rows became four actions.

**What the user gains beyond the rebuild**, because the platform's table brings
it and the QML `ListView` could not:

- **column sorting** — click "Candles" to find the biggest shard, click
  "Status" to bring every shard with holes to the top;
- **a confirmation before `Clear`** — the QML row fired `clear` straight at the
  Presenter with nothing in between, which the Robustness/User-Control
  principles (and `Docs/HLD/11_desktop_workbench.md` §11.5) do not allow for a
  destructive action. It now names the shard and what will be deleted.

**What it keeps**, so the screen that hosts it did not have to change:
`rowActionRequested(action, symbol, interval)` with the same four action
strings, `set_search_text`, `set_actions_enabled`, `set_known_shard_count`.
`root_object` is gone with the QML it exposed.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.empty_page import empty_page
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
    write_value,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import (
    ColumnKind,
    configure_item_view,
)

from ..database_status_table_model import (
    DatabaseStatusFilterProxy,
    DatabaseStatusRow,
    DatabaseStatusTableModel,
)

#: The action strings this panel emits. They are the same four
#: `DatabaseStatusRow.qml` emitted, because `DataManagementView` maps them onto
#: four view-model calls and this rebuild is not the place to renegotiate that
#: contract.
INSPECT_KLINES = "klines"
INSPECT_GAPS = "gaps"
CLEAR_SHARD = "clear"

#: Asked before `Clear` runs. Returns True to proceed. Injectable so a test
#: drives the panel without a modal dialog waiting for a click that never
#: comes — the default below is the real `QMessageBox`.
type ConfirmClear = Callable[[DatabaseStatusRow], bool]


def _empty_text(known_shard_count: int) -> str:
    """`BUG-087`: an empty table does not mean an empty vault. Shards nobody
    has scanned *this session* are on disk and invisible to `rowCount()`, so
    the message branches on the independent count the screen supplies."""
    if known_shard_count > 0:
        return (
            f"Storage Vault has {known_shard_count} local data file(s) on disk, "
            "not yet scanned this session. Choose Data → Scan all shards, or "
            "Data → Sync history… to fetch one."
        )
    return "No history is stored yet. Choose Data → Sync history… to fetch one."


class DatabaseStatusPanel(QWidget):  # base-exempt: a container, not a surface
    """
    @brief The status table for every `(symbol, interval)` shard, with the
    four per-shard actions.

    @details A plain `QWidget` holding a toolbar and a `QTableView`, not the
    kit's `Panel`: that base paints the card chrome — background, border,
    radius — that ADR D21 removed from this app. The `base-exempt` marker
    above answers a ratchet written under the previous doctrine
    (`EPIC-007F`: inherit `Card`/`Panel`/`Overlay`), which ADR D20–D22
    reversed for new desktop widgets.

    @details Constructed from the screen's one real
    `DatabaseStatusTableModel` (`DataManagementViewModel.status_model`); the
    search filter is this panel's own `DatabaseStatusFilterProxy`, so a host
    hands over the raw model and nothing else.
    """

    rowActionRequested = Signal(str, str, str)  # action, symbol, interval
    #: The selected shard (`DatabaseStatusRow`), or `None` when none is.
    shardSelected = Signal(object)

    def __init__(
        self,
        status_model: DatabaseStatusTableModel,
        parent: QWidget | None = None,
        confirm_clear: ConfirmClear | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("databaseStatusPanel")
        self._model = status_model
        self._proxy = DatabaseStatusFilterProxy(self)
        self._proxy.setSourceModel(status_model)
        self._known_shard_count = 0
        self._actions_enabled = True
        self._confirm_clear = confirm_clear or self._ask_before_clearing

        self._count_label = QLabel()
        self._count_label.setObjectName("lblDatabaseStatusCount")
        self._search = QLineEdit()
        self._search.setObjectName("txtDatabaseStatusSearch")
        self._search.setPlaceholderText("Search symbol / timeframe…")
        self._search.setClearButtonEnabled(True)
        self._search.textEdited.connect(self._proxy.set_search_text)
        # `set_search_text()` invalidates the filter without emitting a count
        # signal of its own, so the label and the empty state are refreshed
        # from the same edit that caused them to change.
        self._search.textEdited.connect(lambda _text: self._refresh_counts())

        self._table = self._build_table()
        self._empty = empty_page(_empty_text(0), "lblDatabaseStatusEmpty")

        self._actions = self._build_actions()

        self._build_layout()

        self._model.countsChanged.connect(self._refresh_counts)
        self._refresh_counts()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_table(self) -> QTableView:
        table = QTableView()
        table.setObjectName("tblDatabaseStatus")
        # Columns, sorting and selection from the model's specs (`EPIC-033N`),
        # over the search filter: the spec proxy sorts what the filter keeps.
        self._spec_proxy = configure_item_view(
            table,
            self._proxy,
            DatabaseStatusTableModel.COLUMNS,
            formatter=APP_VALUE_FORMATTER,
        )
        table.sortByColumn(
            DatabaseStatusTableModel.column("symbol"), Qt.SortOrder.AscendingOrder
        )
        table.doubleClicked.connect(lambda _index: self._request(INSPECT_KLINES))
        table.selectionModel().selectionChanged.connect(
            lambda *_args: self._on_selection_changed()
        )
        # Qt renders a widget's own actions as its context menu.
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        return table

    def _build_actions(self) -> dict[str, QAction]:
        """The table's context menu: the Data menu's commands that act on the
        selected shard, by the same names."""
        specs = (
            (INSPECT_GAPS, "&Check gaps", "actInspectGaps"),
            (INSPECT_KLINES, "&Inspect candles", "actInspectKlines"),
            (CLEAR_SHARD, "&Delete data", "actClearShard"),
        )
        actions: dict[str, QAction] = {}
        for action_id, label, object_name in specs:
            action = QAction(label, self)
            action.setObjectName(object_name)
            action.triggered.connect(
                lambda _checked=False, chosen=action_id: self._request(chosen)
            )
            self._table.addAction(action)
            actions[action_id] = action
        return actions

    def _build_layout(self) -> None:
        head = QHBoxLayout()
        head.addWidget(self._count_label)
        head.addStretch(1)
        head.addWidget(self._search)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(head)
        layout.addWidget(self._table, 1)
        layout.addWidget(self._empty, 1)

    # ------------------------------------------------------------------ #
    # The host's surface
    # ------------------------------------------------------------------ #

    def set_search_text(self, text: str) -> None:
        """Programmatic search — the same path typing in the box takes."""
        self._search.setText(text)
        self._proxy.set_search_text(text)
        self._refresh_counts()

    def set_actions_enabled(self, enabled: bool) -> None:
        """`_StatusRowWidget.apply_ui_mode(idle)`'s rule, unchanged: while a
        sync is running, no shard action may be started."""
        self._actions_enabled = enabled
        self._refresh_action_state()

    def set_known_shard_count(self, count: int) -> None:
        if count == self._known_shard_count:
            return
        self._known_shard_count = count
        self._empty.setText(_empty_text(count))

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def selected_row(self) -> DatabaseStatusRow | None:
        """The shard every action operates on, or `None` when none is
        selected."""
        indexes = self._table.selectionModel().selectedRows()
        if not indexes:
            return None
        filtered = self._spec_proxy.mapToSource(indexes[0])
        return self._model.row_for(self._proxy.mapToSource(filtered))

    def visible_row_count(self) -> int:
        """Rows the search leaves visible — what the count label reports."""
        return self._proxy.rowCount()

    def _refresh_counts(self) -> None:
        visible = self.visible_row_count()
        self._count_label.setText(f"{visible} shard{'' if visible == 1 else 's'}")
        self._table.setVisible(visible > 0)
        self._empty.setVisible(visible == 0)
        # A rescan can replace the selected row without a selection change.
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        self._refresh_action_state()
        self.shardSelected.emit(self.selected_row())

    def _refresh_action_state(self) -> None:
        row = self.selected_row()
        for action_id, action in self._actions.items():
            applies = row is not None
            if action_id == INSPECT_GAPS:
                # Was `visible: !isHealthy` on the QML button. Disabled rather
                # than hidden: an action that disappears teaches the user
                # nothing, one that greys out says "not for this shard".
                applies = row is not None and not row.is_healthy
            action.setEnabled(self._actions_enabled and applies)

    # ------------------------------------------------------------------ #
    # Acting
    # ------------------------------------------------------------------ #

    def _request(self, action: str) -> None:
        row = self.selected_row()
        if row is None or not self._actions_enabled:
            return
        if action == INSPECT_GAPS and row.is_healthy:
            return
        if action == CLEAR_SHARD and not self.confirm_clear(row):
            return
        self.rowActionRequested.emit(action, row.symbol, row.interval)

    def confirm_clear(self, row: DatabaseStatusRow) -> bool:
        """The question before `row` is deleted, from the context menu or
        Data → Delete data alike."""
        return self._confirm_clear(row)

    def _ask_before_clearing(self, row: DatabaseStatusRow) -> bool:
        """Names the shard and the consequence, per `HLD §11.5` — deleting
        local candles is not undoable and the row's own button used to do it
        on one click."""
        answer = QMessageBox.question(
            self,
            "Delete Data",
            f"Delete all {write_value(ColumnKind.QUANTITY, row.total_candles)} "
            "locally stored candles for "
            f"{row.symbol} ({row.interval})?\n\n"
            "The data can be downloaded again, but the local copy is removed "
            "now.",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Yes
