"""`EPIC-003F1` — first slice of `BackTestViewModel`'s decomposition
(`EPIC-003F` §4, hướng C — facade chuyển tiếp). Owns exactly the 6
trade-log properties/signals `backtest_view_model.py` used to hold
directly (BOT-057 §2.1); `BackTestViewModel` now forwards to this
instance instead of duplicating the state.

@details Deliberately a plain `QObject`, not `BaseQmlViewModel` — this
sub-ViewModel is never set as a QML context property and never registered
on its own; only `BackTestViewModel`'s facade properties/signals are ever
QML-visible, exactly as before this task (`EPIC-003F1` §2.3 point 1 —
facade first, no call site moves). `unprotected_mutators()`'s cross-thread
guard (`tests/sanity/test_view_model_thread_affinity_sanity.py`) only
scans `BaseQmlViewModel` subclasses for this reason: nothing outside
`BackTestViewModel` ever holds a reference to this class, so every
mutation into it is already gated by the facade's own `@Slot`-protected
entry points — this class needs no `@Slot` of its own.

State accessors are plain Python `@property`, not PySide6 `Property` —
nothing reads this object through Qt's meta-object system (QML never
touches it), so the QML type-marshaling `Property` exists for would be
pure ceremony here. The six `Signal`s stay real PySide6 signals: they are
connected directly to the facade's own signals of the same shape
(`backtest_view_model.py`'s `self._trade_log.rowsChanged.connect(self.
tradeLogRowsChanged)`, one per signal, `EPIC-003F1` §3.2), which requires
genuine `QObject` signals on both ends.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.TradeLogTable.trade_log_filter import (
    TradeLogFilter,
)


class TradeLogViewModel(QObject):
    """@brief State behind the Backtest screen's Trade Log table — rows,
    filter, search text, pagination. See module docstring for why this is
    a plain `QObject` with plain-Python properties."""

    filterChanged = Signal()
    searchTextChanged = Signal()
    currentPageChanged = Signal()
    #: Covers rows/totalCount/totalPages together — the Presenter always
    #: recomputes and sets all 3 in one call (same bundling
    #: `set_stat_cards` uses for primary/extendedStatCards).
    rowsChanged = Signal()
    #: Emitted whenever filter/searchText/currentPage changes — distinct
    #: from those properties' own notify signals because the Presenter
    #: needs ONE place to listen and recompute the filtered/paginated row
    #: set (BOT-057).
    queryChanged = Signal()
    #: Emitted when the user clicks "Export" (BOT-057 §2.1).
    exportRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, str]] = []
        self._total_count = 0
        self._total_pages = 1
        self._filter = TradeLogFilter.ALL.value
        self._search_text = ""
        self._current_page = 1

    @property
    def rows(self) -> list[dict[str, str]]:
        """Already-formatted display rows for the CURRENT page only — the
        Presenter owns filtering/searching/pagination over the full trade
        list, this is just whatever it decided to render right now."""
        return self._rows

    @property
    def totalCount(self) -> int:
        """Row count AFTER filter/search, BEFORE pagination — the "44
        Lệnh" badge counts what matches the current filter, not the page
        size."""
        return self._total_count

    @property
    def totalPages(self) -> int:
        return self._total_pages

    def set_page_state(
        self,
        rows: list[dict[str, str]],
        total_count: int,
        total_pages: int,
    ) -> None:
        """Bulk-write, called only by `BackTestViewModel`'s own
        `set_trade_log_page_state` — same convention `set_stat_cards`
        uses on the facade."""
        self._rows = rows
        self._total_count = total_count
        self._total_pages = total_pages
        self.rowsChanged.emit()

    @property
    def filter(self) -> str:
        return self._filter

    @filter.setter
    def filter(self, value: str) -> None:
        """One of `TradeLogFilter`'s values. Resets to page 1 on change:
        a filter narrowing the result set could otherwise leave the view
        stuck on a now out-of-range page."""
        if value != self._filter:
            self._filter = value
            self._current_page = 1
            self.filterChanged.emit()
            self.currentPageChanged.emit()
            self.queryChanged.emit()

    @property
    def searchText(self) -> str:
        return self._search_text

    @searchText.setter
    def searchText(self, value: str) -> None:
        if value != self._search_text:
            self._search_text = value
            self._current_page = 1
            self.searchTextChanged.emit()
            self.currentPageChanged.emit()
            self.queryChanged.emit()

    @property
    def currentPage(self) -> int:
        return self._current_page

    @currentPage.setter
    def currentPage(self, value: int) -> None:
        if value != self._current_page:
            self._current_page = value
            self.currentPageChanged.emit()
            self.queryChanged.emit()

    def request_export(self) -> None:
        """Called only by `BackTestViewModel.requestTradeLogExport()`."""
        self.exportRequested.emit()
