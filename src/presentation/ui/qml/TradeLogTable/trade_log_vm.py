"""State behind `TradeLogTable.qml` — reuses the exact same pure filtering
and formatting `BackTestTradeLogsPanel` (QtWidgets) already runs, unchanged.

Two additive design changes from the QtWidgets version, not a rewrite of it
(`qml-rule.md` §0.2 — "không ngại đổi design" when a feature does not fit):

1. **No pagination.** `trade_log_pagination.py` exists because a `QWidget`
   per row was expensive at Backtest's real scale ("hàng nghìn" — that
   module's own comment). A QML `ListView(reuseItems: true)` virtualizes
   instead — the same reason `SymbolPicker`'s `GridView` renders 1000
   symbols with only the visible cards instantiated (`EPIC-015` §4b).
   `rows` below is the full filtered list; pagination becomes unnecessary
   for this renderer, not merely deferred.
2. **Per-filter counts.** The current QtWidgets tabs (`_filter_tab_button.py`)
   show only a label — no count. The mockup adds one per tab; computing it
   is one more call to the already-tested `filter_trade_log_rows`, not new
   filtering logic.

Search, export, and column sort are deferred, not redesigned — see
NOTES.md. Row expand (entry/exit reason, metadata — `BOT-045`) is built:
`trade_log_row_to_qml` already returns `entryReasonText`/`exitReasonText`/
`durationText`/`metadataItems`, so expanding a row costs one more boolean
per row here, not new formatting.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal, Slot
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_filter import (
    TradeLogFilter,
    filter_trade_log_rows,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.trade_log_row import (
    TradeLogRow,
    trade_log_rows_to_qml,
)

#: Same five tabs, same order and labels, as `_FILTER_TABS` in
#: `backtest_trade_logs_panel.py` — this is the one place their Vietnamese
#: text is allowed to duplicate that file's, since neither imports the other
#: (this widget stands alone until it is wired to a real screen, NOTES.md).
_FILTER_ORDER: tuple[TradeLogFilter, ...] = (
    TradeLogFilter.ALL,
    TradeLogFilter.LONG,
    TradeLogFilter.SHORT,
    TradeLogFilter.WIN,
    TradeLogFilter.LOSS,
)

_FILTER_LABELS: dict[TradeLogFilter, str] = {
    TradeLogFilter.ALL: "Tất cả",
    TradeLogFilter.LONG: "Mua (LONG)",
    TradeLogFilter.SHORT: "Bán (SHORT)",
    TradeLogFilter.WIN: "Lệnh thắng",
    TradeLogFilter.LOSS: "Lệnh thua",
}


class TradeLogVM(QObject):
    """
    @brief The full trade list for one backtest run, split into 5 filter
    tabs with live counts, and the currently-visible (filtered) rows.

    @details Callback-constructed, not handed `BackTestViewModel` directly
    — same reasoning as `SelectListVM`/`TimeframeVM`: this widget has no
    opinion about which screen owns it, and its tests need one lambda, no
    `QApplication`. `get_timezone_name` mirrors
    `BackTestTradeLogsPanel`'s display-timezone dependency (`BOT-097`) —
    entry/exit times render in whatever timezone the user picked, not
    always UTC.
    """

    stateChanged = Signal()

    def __init__(
        self,
        *,
        get_rows: Callable[[], Sequence[TradeLogRow]],
        get_timezone_name: Callable[[], str],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_rows = get_rows
        self._get_timezone_name = get_timezone_name
        self._filter = TradeLogFilter.ALL
        self._all_rows: list[TradeLogRow] = []
        self._tabs: list[dict[str, object]] = []
        self._rows: list[dict[str, object]] = []
        #: Trade `index` values (the stable, 1-based identity
        #: `TradeLogRow.index` documents), not list position — a row's
        #: expanded state must survive a filter change moving it around.
        self._expanded: set[int] = set()

    @Property("QVariantList", notify=stateChanged)
    def filterTabs(self) -> list[dict[str, object]]:
        return self._tabs

    @Property("QVariantList", notify=stateChanged)
    def rows(self) -> list[dict[str, object]]:
        return self._rows

    @Property(int, notify=stateChanged)
    def totalCount(self) -> int:
        return len(self._all_rows)

    def refresh(self) -> None:
        """Re-reads the trade list from the host and rebuilds both the tab
        counts and the visible rows."""
        self._all_rows = list(self._get_rows())
        self._recompute()

    @Slot(str)
    def chooseFilter(self, filter_id: str) -> None:
        try:
            chosen = TradeLogFilter(filter_id)
        except ValueError:
            return
        if chosen is self._filter:
            return
        self._filter = chosen
        self._recompute()

    @Slot(int)
    def toggleExpanded(self, index: int) -> None:
        if index in self._expanded:
            self._expanded.discard(index)
        else:
            self._expanded.add(index)
        self._recompute()

    def _recompute(self) -> None:
        self._tabs = [
            {
                "id": kind.value,
                "label": _FILTER_LABELS[kind],
                "count": len(filter_trade_log_rows(self._all_rows, kind)),
                "selected": kind is self._filter,
            }
            for kind in _FILTER_ORDER
        ]
        visible = filter_trade_log_rows(self._all_rows, self._filter)
        formatted = trade_log_rows_to_qml(visible, tz_name=self._get_timezone_name())
        for row, trade in zip(formatted, visible, strict=True):
            row["expanded"] = trade.index in self._expanded
        self._rows = formatted
        self.stateChanged.emit()
