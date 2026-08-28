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

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...kit import (
    Overlay,
    StyledField,
    StyleRole,
    Tab,
    TabBar,
    apply_role,
)
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
from .symbol_card import SymbolCard

_TITLE = "CHỌN SYMBOL"
_SEARCH_PLACEHOLDER = "Tìm symbol (vd: BTC)"
_LOADING_TEXT = "Đang tải danh sách symbol từ sàn..."
_NO_MATCH_TEXT = "Không có symbol nào khớp bộ lọc hiện tại."

_FAVOURITES_HEADING = "YÊU THÍCH"
_RESULTS_HEADING = "TẤT CẢ KẾT QUẢ"
_RESULT_COUNT_TEXT = "{count} kết quả"
_CURRENT_FOOTER_TEXT = "Đang dùng: {symbol}"
_KEY_HINTS = "↑↓ di chuyển   ↵ chọn   ☆ yêu thích"

_SCOPE_TABS = (
    (Scope.ALL, "Tất cả"),
    (Scope.FAVOURITES, "Yêu thích"),
    (Scope.RECENT, "Gần đây"),
)
_QUOTE_ANY_LABEL = "Tất cả"

#: Symbols are short, so three to a row reads as a keypad rather than a list —
#: the shape both existing dialogs already rendered.
_COLUMNS = 3

#: How many quote tabs to offer beyond "Tất cả". The exchange quotes in more
#: than a dozen assets; past the top few the tab bar wraps and stops being
#: scannable, and the search box covers the rest.
_MAX_QUOTE_TABS = 3

#: How many recently chosen symbols a caller is expected to keep. Declared
#: here, next to the picker that gives the list its meaning, so every screen
#: remembers the same depth.
RECENT_LIMIT = 8


class SymbolPickerOverlay(Overlay):
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

    def __init__(
        self,
        get_symbols: Callable[[], Sequence[str]],
        get_favourites: Callable[[], Sequence[str]],
        get_recents: Callable[[], Sequence[str]],
        get_current: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("symbolPickerModal")
        self.resize(720, 620)

        self._get_symbols = get_symbols
        self._get_favourites = get_favourites
        self._get_recents = get_recents
        self._get_current = get_current

        self._filter = FilterState()
        self._cards: list[SymbolCard] = []
        self._focused_index = -1

        self._build_search_row()
        self._build_filter_rows()
        self._build_results_area()
        self._build_footer_row()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_search_row(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        self._search_field = StyledField()
        self._search_field.setObjectName("txtSymbolSearch")
        self._search_field.setPlaceholderText(_SEARCH_PLACEHOLDER)
        self._search_field.setClearButtonEnabled(True)
        self._search_field.textChanged.connect(self._on_search_changed)
        row.addWidget(self._search_field, 1)

        self._result_count = QLabel()
        self._result_count.setObjectName("lblSymbolResultCount")
        apply_role(self._result_count, StyleRole.CAPTION)
        row.addWidget(self._result_count)
        self.body_layout.addLayout(row)

    def _build_filter_rows(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)

        self._scope_tabs = TabBar()
        self._scope_tabs.setObjectName("tabsSymbolScope")
        self._scope_tabs.tab_selected.connect(self._on_scope_selected)
        row.addWidget(self._scope_tabs)

        row.addStretch(1)

        self._quote_tabs = TabBar()
        self._quote_tabs.setObjectName("tabsSymbolQuote")
        self._quote_tabs.tab_selected.connect(self._on_quote_selected)
        row.addWidget(self._quote_tabs)
        self.body_layout.addLayout(row)

    def _build_results_area(self) -> None:
        self._status_label = QLabel(_LOADING_TEXT)
        self._status_label.setObjectName("lblSymbolStatus")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_role(self._status_label, StyleRole.CAPTION)
        self.body_layout.addWidget(self._status_label)

        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(14)

        self._favourites_heading = self._section_heading(_FAVOURITES_HEADING)
        self._favourites_grid = QGridLayout()
        self._favourites_grid.setSpacing(8)
        self._content_layout.addWidget(self._favourites_heading)
        self._content_layout.addLayout(self._favourites_grid)

        self._results_heading = self._section_heading(_RESULTS_HEADING)
        self._results_grid = QGridLayout()
        self._results_grid.setSpacing(8)
        self._content_layout.addWidget(self._results_heading)
        self._content_layout.addLayout(self._results_grid)
        self._content_layout.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidget(content)
        apply_role(self._scroll, StyleRole.LIST_SURFACE)
        self.body_layout.addWidget(self._scroll, 1)

    def _build_footer_row(self) -> None:
        row = QHBoxLayout()
        hints = QLabel(_KEY_HINTS)
        hints.setObjectName("lblSymbolKeyHints")
        apply_role(hints, StyleRole.CAPTION)
        row.addWidget(hints)
        row.addStretch(1)
        self._current_label = QLabel()
        self._current_label.setObjectName("lblSymbolCurrent")
        apply_role(self._current_label, StyleRole.CAPTION)
        row.addWidget(self._current_label)
        self.body_layout.addLayout(row)

    @staticmethod
    def _section_heading(text: str) -> QLabel:
        label = QLabel(text)
        apply_role(label, StyleRole.SECTION_LABEL)
        return label

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
        self._scope_tabs.set_tabs(
            [
                Tab(
                    id=scope.value,
                    label=label,
                    badge=str(favourite_count)
                    if scope is Scope.FAVOURITES and favourite_count
                    else "",
                )
                for scope, label in _SCOPE_TABS
            ]
        )
        self._scope_tabs.set_current_id(self._filter.scope.value)

    def _sync_quote_tabs(self) -> None:
        quotes = available_quotes(self._entries)[:_MAX_QUOTE_TABS]
        self._quote_tabs.set_tabs(
            [Tab(id=QUOTE_ANY, label=_QUOTE_ANY_LABEL)]
            + [Tab(id=quote, label=quote) for quote in quotes]
        )
        # A quote tab can vanish between opens (the exchange delists the last
        # pair in it). Falling back to "Tất cả" beats leaving the filter set
        # to something with no tab, which would render an empty grid the user
        # cannot undo.
        if self._filter.quote != QUOTE_ANY and self._filter.quote not in quotes:
            self._filter = FilterState(
                query=self._filter.query, scope=self._filter.scope, quote=QUOTE_ANY
            )
        self._quote_tabs.set_current_id(self._filter.quote)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _rebuild(self) -> None:
        self._clear_grid(self._favourites_grid)
        self._clear_grid(self._results_grid)
        self._cards = []
        self._focused_index = -1

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
        self._scroll.setVisible(True)

        # Favourites are only given their own section when they are not the
        # whole list — on the "Yêu thích" tab a heading over every row, and an
        # empty "all results" heading under it, is noise.
        show_split = bool(favourites) and self._filter.scope is not Scope.FAVOURITES
        if show_split:
            self._fill_grid(self._favourites_grid, favourites)
            self._fill_grid(self._results_grid, rest)
        else:
            self._fill_grid(self._results_grid, visible)

        self._favourites_heading.setVisible(show_split)
        self._results_heading.setVisible(show_split and bool(rest))

    def _show_status(self, text: str) -> None:
        self._status_label.setText(text)
        self._status_label.setVisible(True)
        self._scroll.setVisible(False)
        self._favourites_heading.setVisible(False)
        self._results_heading.setVisible(False)

    def _fill_grid(self, grid: QGridLayout, entries: Sequence[SymbolEntry]) -> None:
        for index, entry in enumerate(entries):
            card = SymbolCard(entry)
            card.clicked.connect(lambda symbol=entry.symbol: self._choose(symbol))
            card.favourite_toggled.connect(self.favourite_toggled)
            grid.addWidget(card, index // _COLUMNS, index % _COLUMNS)
            self._cards.append(card)

    @staticmethod
    def _clear_grid(grid: QGridLayout) -> None:
        while grid.count():
            entry = grid.takeAt(0)
            if entry is None:  # pragma: no cover - count() > 0 guarantees one
                break
            widget = entry.widget()
            if widget is not None:
                widget.deleteLater()

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
        """Arrow keys move a highlight, Enter chooses it.

        Typing stays in the search box the whole time — a grid of this size is
        faster typed than clicked, and forcing the user to leave the field to
        reach the result they just narrowed to would undo that.
        """
        key = event.key()
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self._cards:
            step = 1 if key == Qt.Key.Key_Down else -1
            self._move_focus(step)
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._cards:
            index = max(self._focused_index, 0)
            self._choose(self._cards[index].entry.symbol)
            event.accept()
            return
        super().keyPressEvent(event)

    def _move_focus(self, step: int) -> None:
        count = len(self._cards)
        self._focused_index = (self._focused_index + step) % count
        for index, card in enumerate(self._cards):
            card.selected = index == self._focused_index
        self._scroll.ensureWidgetVisible(self._cards[self._focused_index])
