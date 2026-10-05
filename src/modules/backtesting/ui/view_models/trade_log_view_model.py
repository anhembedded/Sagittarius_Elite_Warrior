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
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_filter import (
    TradeLogFilter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.trade_log_row import (
    TradeLogRow,
)


class TradeLogViewModel(QObject):
    """@brief State behind the Backtest mode's Trades table — the rows that
    match, the filter and the search text. See module docstring for why this
    is a plain `QObject` with plain-Python properties.

    @details `EPIC-033L` dropped the page: the rows were a hand-built list
    shown twenty at a time; a `QTableView` scrolls any number, so every
    matching row is here and the page number and count went with the
    pager."""

    filterChanged = Signal()
    searchTextChanged = Signal()
    #: Covers `rows` and `totalCount` together — the Presenter always
    #: recomputes and sets both in one call.
    rowsChanged = Signal()
    #: Emitted whenever the filter or the search text changes — distinct from
    #: those properties' own notify signals because the Presenter needs ONE
    #: place to listen and recompute the matching rows (BOT-057).
    queryChanged = Signal()
    #: Emitted by Tools → Export trades… (BOT-057 §2.1).
    exportRequested = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[TradeLogRow] = []
        self._filter = TradeLogFilter.ALL.value
        self._search_text = ""

    @property
    def rows(self) -> list[TradeLogRow]:
        """The trades matching the current filter and search — the Presenter
        owns filtering and searching over the full trade list."""
        return self._rows

    @property
    def totalCount(self) -> int:
        """How many trades match the current filter and search."""
        return len(self._rows)

    def set_rows(self, rows: list[TradeLogRow]) -> None:
        """Bulk-write, called only by the trade log coordinator."""
        self._rows = rows
        self.rowsChanged.emit()

    @property
    def filter(self) -> str:
        return self._filter

    @filter.setter
    def filter(self, value: str) -> None:
        """One of `TradeLogFilter`'s values."""
        if value != self._filter:
            self._filter = value
            self.filterChanged.emit()
            self.queryChanged.emit()

    @property
    def searchText(self) -> str:
        return self._search_text

    @searchText.setter
    def searchText(self, value: str) -> None:
        if value != self._search_text:
            self._search_text = value
            self.searchTextChanged.emit()
            self.queryChanged.emit()

    def request_export(self) -> None:
        """Called by Tools → Export trades…."""
        self.exportRequested.emit()
