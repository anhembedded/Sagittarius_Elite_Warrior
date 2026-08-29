"""State behind `KlineInspectorTable.qml` — reuses the same row conversion
`KLineInspectorTableModel` (QtWidgets) already runs, unchanged.

Design change from that model, not a copy of it (`qml-rule.md` §0.2 —
"không ngại đổi design" when a feature does not fit): no pagination.
`KLineInspectorTableModel` paginates in memory because a `QWidget` per row
was expensive; the fetch itself is already bounded
(`KLineInspectorCoordinator.run_inspect_klines` caps every fetch at 10,000
candles), and a QML `ListView(reuseItems: true)` virtualizes 10,000 rows
the same way `SymbolPicker`'s `GridView` renders 1000 symbols with only the
visible cards instantiated (`EPIC-015` §4b). `rows` below is the full
list — there is no page to be on.

Audit ("Kiểm định Dữ liệu") and jump-to-date are deferred, not redesigned —
see NOTES.md.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Property, QObject, Signal
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.kline_inspector_table_model import (
    kline_display_row_to_qml,
    market_data_to_kline_row,
)


class KlineInspectorVM(QObject):
    """
    @brief The full candle list for one symbol/interval shard, already
    formatted for display.

    @details Callback-constructed, not handed a screen ViewModel — same
    reasoning as `SelectListVM`/`TradeLogVM`: this widget has no opinion
    about which screen owns it, and its tests need three lambdas, no
    `QApplication`.
    """

    stateChanged = Signal()

    def __init__(
        self,
        *,
        get_klines: Callable[[], Sequence[MarketData]],
        get_symbol: Callable[[], str],
        get_interval: Callable[[], str],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_klines = get_klines
        self._get_symbol = get_symbol
        self._get_interval = get_interval
        self._rows: list[dict[str, object]] = []
        self._symbol = ""
        self._interval = ""

    @Property("QVariantList", notify=stateChanged)
    def rows(self) -> list[dict[str, object]]:
        return self._rows

    @Property(int, notify=stateChanged)
    def rowCount(self) -> int:
        return len(self._rows)

    @Property(str, notify=stateChanged)
    def symbol(self) -> str:
        return self._symbol

    @Property(str, notify=stateChanged)
    def interval(self) -> str:
        return self._interval

    def refresh(self) -> None:
        """Re-reads the candle list and symbol/interval from the host."""
        self._symbol = self._get_symbol()
        self._interval = self._get_interval()
        self._rows = [
            kline_display_row_to_qml(market_data_to_kline_row(k))
            for k in self._get_klines()
        ]
        self.stateChanged.emit()
