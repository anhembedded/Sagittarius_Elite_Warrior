"""`SymbolPickerOverlay` — choose a trading pair. Shared by every screen.

Replaces two dialogs that rendered the same shape differently: Data
Management reached the old thin `SymbolPickerOverlay`, Backtest kept its own
`BacktestSymbolPickerDialog`, and Dev Board had no picker at all — an editable
`QComboBox` seeded with two hardcoded symbols. `EPIC-007F` recorded the
intent to converge them and did not get there; this is that convergence, with
the behaviour a fourteen-hundred-entry list actually needs:

- favourites, pinned above the results and starrable without choosing;
- recents, so the pair used ten minutes ago is one click away;
- a quote filter, because "every USDT pair" is a real question;
- keyboard navigation, because a grid this size is faster typed than clicked.

Favourites and recents are supplied and stored by the caller (a screen's own
`IStateContributor`, per `EPIC-010`'s ui_state) rather than held here: a
dialog that owned them would either share one list across screens that want
their own, or reinvent persistence this app already has.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTabBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    APP_VALUE_FORMATTER,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import configure_item_view

from .filtering import (
    QUOTE_ANY,
    FilterState,
    Scope,
    SymbolEntry,
    apply_filter,
    available_quotes,
    build_entries,
    partition_favourites,
)
from .symbol_table_model import SymbolTableModel

_TITLE = "Select Symbol"
_SEARCH_PLACEHOLDER = "Search symbol (e.g. BTC)"
_LOADING_TEXT = "Loading symbol list from the exchange..."
_NO_MATCH_TEXT = "No symbol matches the current filter."

_RESULT_COUNT_TEXT = "{count} results"
_CURRENT_FOOTER_TEXT = "Current: {symbol}"
_KEY_HINTS = "↑↓ move   ↵ select   ☆ favourite"

#: How much of the list a fresh dialog shows, in average characters wide and
#: text lines tall of the system font, so the size follows the font and not a
#: pixel count written here.
_WIDTH_CHARS = 64
_HEIGHT_LINES = 26

_SCOPE_TABS = (
    (Scope.ALL, "All"),
    (Scope.FAVOURITES, "Favourites"),
    (Scope.RECENT, "Recent"),
)
_QUOTE_ANY_LABEL = "All"

#: How many quote tabs to offer beyond "All". The exchange quotes in more
#: than a dozen assets; past the top few the tab bar wraps and stops being
#: scannable, and the search box covers the rest.
_MAX_QUOTE_TABS = 3

#: How many recently chosen symbols a caller is expected to keep. Declared
#: here, next to the picker that gives the list its meaning, so every screen
#: remembers the same depth.
RECENT_LIMIT = 8


def _fill_tabs(bar: QTabBar, tabs: Sequence[tuple[str, str]], current_id: str) -> None:
    """Shows `tabs` (id, label) in `bar` with `current_id` selected, without
    raising `currentChanged`: only the user's click is a selection."""
    bar.blockSignals(True)
    try:
        while bar.count():
            bar.removeTab(0)
        for tab_id, label in tabs:
            bar.setTabData(bar.addTab(label), tab_id)
        for index in range(bar.count()):
            if bar.tabData(index) == current_id:
                bar.setCurrentIndex(index)
                break
    finally:
        bar.blockSignals(False)


class SymbolPickerOverlay(QDialog):
    """
    @brief A modal, searchable, filterable grid of tradable pairs.

    @details Choosing emits `symbol_chosen` and closes — unlike the generic
    `PickerOverlay`, which leaves closing to its consumer because one of the
    app's pickers must stay open. There is nothing to stay open for here.

    Starring emits `favourite_toggled` and does NOT close, which is the whole
    reason this is not a `PickerOverlay` subclass: that base builds one
    clickable card per item and knows nothing about a second action inside a
    row, or about sections, or about a filter that is not the search box.
    """

    symbol_chosen = Signal(str)
    favourite_toggled = Signal(str)

    #: Emitted on every open, **before** the lists are re-read: "if your symbol
    #: list can be refetched, now is the time".
    #:
    #: Added in PR 4.3b, and it is a promise carried over rather than a new
    #: idea. The QML picker this replaces raised it — Backtest connects it to
    #: `refreshSymbolOptionsRequested` (`signal_wiring.py`) and Dev Board to
    #: `symbolOptionsRefreshRequested` (`dashboard_presenter.py`) — and without
    #: it a user who opened the picker before the exchange's list had arrived
    #: would sit on "Loading…" until they closed and reopened. Data Management
    #: connects nothing: its own scan is what populates the list.
    refresh_requested = Signal()

    def __init__(
        self,
        get_symbols: Callable[[], Sequence[str]],
        get_favourites: Callable[[], Sequence[str]],
        get_recents: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("symbolPickerModal")
        self.setWindowTitle(_TITLE)
        self.setModal(True)
        self._body_layout = QVBoxLayout(self)

        self._get_symbols = get_symbols
        self._get_favourites = get_favourites
        self._get_recents = get_recents
        self._get_current = get_current

        self._filter = FilterState()
        self._entries: list[SymbolEntry] = []
        self._model = SymbolTableModel(self)

        self._build_search_row()
        self._build_filter_rows()
        self._build_results_area()
        self._build_footer_row()
        self._build_button_box()

    def sizeHint(self) -> QSize:
        """Sized by the system font: a screenful of rows, never a pixel count."""
        base = super().sizeHint()
        metrics = self.fontMetrics()
        return QSize(
            max(base.width(), metrics.averageCharWidth() * _WIDTH_CHARS),
            max(base.height(), metrics.lineSpacing() * _HEIGHT_LINES),
        )

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_search_row(self) -> None:
        row = QHBoxLayout()
        self._search_field = QLineEdit()
        self._search_field.setObjectName("txtSymbolSearch")
        self._search_field.setPlaceholderText(_SEARCH_PLACEHOLDER)
        self._search_field.setClearButtonEnabled(True)
        self._search_field.textChanged.connect(self._on_search_changed)
        row.addWidget(self._search_field, 1)

        self._result_count = QLabel()
        self._result_count.setObjectName("lblSymbolResultCount")
        row.addWidget(self._result_count)
        self._body_layout.addLayout(row)

    def _build_filter_rows(self) -> None:
        row = QHBoxLayout()

        self._scope_tabs = QTabBar()
        self._scope_tabs.setObjectName("tabsSymbolScope")
        self._scope_tabs.currentChanged.connect(
            lambda index: self._on_scope_selected(
                index, str(self._scope_tabs.tabData(index))
            )
        )
        row.addWidget(self._scope_tabs)

        row.addStretch(1)

        self._quote_tabs = QTabBar()
        self._quote_tabs.setObjectName("tabsSymbolQuote")
        self._quote_tabs.currentChanged.connect(
            lambda index: self._on_quote_selected(
                index, str(self._quote_tabs.tabData(index))
            )
        )
        row.addWidget(self._quote_tabs)
        self._body_layout.addLayout(row)

    def _build_results_area(self) -> None:
        self._status_label = QLabel(_LOADING_TEXT)
        self._status_label.setObjectName("lblSymbolStatus")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._body_layout.addWidget(self._status_label)

        self._table = QTableView()
        self._table.setObjectName("tblSymbolResults")
        # Whole-row, one row at a time, read-only: the one way every table of
        # the application behaves (`EPIC-033N`); a user who clicked a cell
        # meant the pair it belongs to.
        self._proxy = configure_item_view(
            self._table,
            self._model,
            SymbolTableModel.COLUMNS,
            formatter=APP_VALUE_FORMATTER,
        )
        self._table.setShowGrid(False)
        # No headers: "Symbol" over a column of symbols in a dialog called
        # SELECT SYMBOL is a label for something the user is already looking at,
        # and the other two columns have nothing to say in a header. Hidden,
        # the header also cannot re-sort the list, whose order is the picker's.
        self._table.horizontalHeader().setVisible(False)
        self._table.clicked.connect(self._on_cell_clicked)
        self._body_layout.addWidget(self._table, 1)

    def _build_footer_row(self) -> None:
        row = QHBoxLayout()
        hints = QLabel(_KEY_HINTS)
        hints.setObjectName("lblSymbolKeyHints")
        row.addWidget(hints)
        row.addStretch(1)
        self._current_label = QLabel()
        self._current_label.setObjectName("lblSymbolCurrent")
        row.addWidget(self._current_label)
        self._body_layout.addLayout(row)

    def _build_button_box(self) -> None:
        """Close is the only commit button: choosing is a click or Enter on a
        row, and Esc closes as well."""
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        close.setObjectName("btnSymbolPickerClose")
        close.setAutoDefault(False)
        buttons.rejected.connect(self.reject)
        self._body_layout.addWidget(buttons)

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #

    def showEvent(self, event) -> None:
        """Refetches everything on every open.

        The exchange's list arrives asynchronously and can still be empty on
        the first open (hence `_LOADING_TEXT`), and favourites/recents change
        between opens. Reading them here rather than in `__init__` is what
        lets the dialog be built once and reused, which is how both consuming
        screens hold it.
        """
        self._search_field.clear()
        self._filter = FilterState()
        # Before `refresh()`, not after: a host that refetches synchronously
        # then has its new list read by the same open, and one that refetches
        # asynchronously calls `refresh()` itself when the answer lands.
        self.refresh_requested.emit()
        self.refresh()
        self._search_field.setFocus()
        super().showEvent(event)

    def refresh(self) -> None:
        """Re-reads the source data and re-renders. Public so a screen whose
        symbol list arrives late can call it without reopening the dialog."""
        self._entries = build_entries(
            self._get_symbols(),
            favourites=self._get_favourites(),
            recents=self._get_recents(),
            current=self._get_current(),
        )
        self._sync_quote_tabs()
        self._sync_scope_tabs()
        self._rebuild()

    def _sync_scope_tabs(self) -> None:
        favourite_count = sum(1 for entry in self._entries if entry.is_favourite)
        _fill_tabs(
            self._scope_tabs,
            [
                (
                    scope.value,
                    f"{label} ({favourite_count})"
                    if scope is Scope.FAVOURITES and favourite_count
                    else label,
                )
                for scope, label in _SCOPE_TABS
            ],
            self._filter.scope.value,
        )

    def _sync_quote_tabs(self) -> None:
        quotes = available_quotes(self._entries)[:_MAX_QUOTE_TABS]
        # A quote tab can vanish between opens (the exchange delists the last
        # pair in it). Falling back to "All" beats leaving the filter set
        # to something with no tab, which would render an empty grid the user
        # cannot undo.
        if self._filter.quote != QUOTE_ANY and self._filter.quote not in quotes:
            self._filter = FilterState(
                query=self._filter.query, scope=self._filter.scope, quote=QUOTE_ANY
            )
        _fill_tabs(
            self._quote_tabs,
            [(QUOTE_ANY, _QUOTE_ANY_LABEL), *((quote, quote) for quote in quotes)],
            self._filter.quote,
        )

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _rebuild(self) -> None:
        has_symbols = bool(self._entries)
        visible = apply_filter(self._entries, self._filter) if has_symbols else []
        favourites, rest = partition_favourites(visible)

        self._result_count.setText(_RESULT_COUNT_TEXT.format(count=len(visible)))
        self._current_label.setText(
            _CURRENT_FOOTER_TEXT.format(symbol=self._get_current() or "—")
        )

        if not has_symbols:
            self._show_status(_LOADING_TEXT)
            return
        if not visible:
            self._show_status(_NO_MATCH_TEXT)
            return

        self._status_label.setVisible(False)
        self._table.setVisible(True)

        # Favourites first, then the rest, both in the order the filter
        # produced. The two section *headings* went with the card grid in PR
        # 4.3a and the pinning did not: a heading over a `QTableView` cannot
        # be virtualised, and on the Favourites tab it labelled every row
        # anyway. What tells a favourite apart is now the filled star in its
        # own column, on the row itself, which is also what the user clicks.
        self._model.set_rows([*favourites, *rest])

        # A chooser opens with something under the keyboard, so Enter works
        # without an arrow key first — and it is the current symbol's row when
        # the filter still admits it.
        self._select_initial_row()

    def _show_status(self, text: str) -> None:
        self._status_label.setText(text)
        self._status_label.setVisible(True)
        self._table.setVisible(False)
        self._model.clear()

    def _select_initial_row(self) -> None:
        rows = self._model.rows
        if not rows:
            return
        current = self._get_current()
        index = next((i for i, entry in enumerate(rows) if entry.symbol == current), 0)
        self._focus_row(index)

    def _focus_row(self, row: int) -> None:
        index = self._proxy.mapFromSource(
            self._model.index(row, SymbolTableModel.SYMBOL_COLUMN)
        )
        self._table.setCurrentIndex(index)
        self._table.scrollTo(index)

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        """Starring is not choosing, and the column is what says which.

        The card this replaced carried a separate `favourite_toggled` button;
        a `QTableView` reports the index it was clicked on, so the same
        distinction is a column comparison instead of a second widget per row.
        """
        entry = self._model.row_for(self._proxy.mapToSource(index))
        if entry is None:
            return
        if index.column() == SymbolTableModel.FAVOURITE_COLUMN:
            self.favourite_toggled.emit(entry.symbol)
            return
        self._choose(entry.symbol)

    # ------------------------------------------------------------------ #
    # Interaction
    # ------------------------------------------------------------------ #

    def _on_search_changed(self, text: str) -> None:
        self._filter = FilterState(
            query=text, scope=self._filter.scope, quote=self._filter.quote
        )
        self._rebuild()

    def _on_scope_selected(self, _index: int, tab_id: str) -> None:
        self._filter = FilterState(
            query=self._filter.query, scope=Scope(tab_id), quote=self._filter.quote
        )
        self._rebuild()

    def _on_quote_selected(self, _index: int, tab_id: str) -> None:
        self._filter = FilterState(
            query=self._filter.query, scope=self._filter.scope, quote=tab_id
        )
        self._rebuild()

    def _choose(self, symbol: str) -> None:
        self.symbol_chosen.emit(symbol)
        self.accept()

    def keyPressEvent(self, event) -> None:
        """Arrow keys move the highlight, Enter chooses it.

        Typing stays in the search box the whole time — a list of this size is
        faster typed than clicked, and forcing the user to leave the field to
        reach the result they just narrowed to would undo that. So the dialog
        intercepts the arrows rather than giving the table focus; the table is
        what *shows* the highlight, and `setCurrentIndex` is what moves it.

        The wrap-around is kept from the card grid: at the bottom of a
        fourteen-hundred-row list, Down reaching the top again is faster than
        scrolling back.
        """
        key = event.key()
        count = self._model.rowCount()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and count:
            step = 1 if key == Qt.Key.Key_Down else -1
            self._focus_row((self._current_row() + step) % count)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and count:
            entry = self._model.rows[self._current_row()]
            self._choose(entry.symbol)
            event.accept()
            return
        super().keyPressEvent(event)

    def _current_row(self) -> int:
        """The model row the highlight is on."""
        index = self._proxy.mapToSource(self._table.currentIndex())
        return index.row() if index.isValid() else 0
