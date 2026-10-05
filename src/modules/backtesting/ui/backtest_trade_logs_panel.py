"""The Backtest mode's Trades panel (`EPIC-033L`, HLD §11.2.1: "bottom:
Trades").

Above the table, which trades to show (a filter and a search); the table of
the trades that match, built from its column specs (`trade_table_model.py`);
under it, the selected trade's journal (`trade_details()`). Selecting a trade
draws its entry and exit on the chart (`PROP-001`); Tools → Export trades…
writes the listed trades to a CSV file.

It replaces a hand-built list: a header strip and rows of styled labels,
twenty to a page with Previous and Next buttons, each row expanding in
place; filter "tabs" that were checkable push buttons; a styled search box
and an Export button repeating no command. Drawdown and Monthly returns, once
tabs of this panel's own tab bar, are docks of their own beside it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import (
    ZonedValueFormatter,
)

from .logic.trade_log_filter import TradeLogFilter
from .logic.trade_log_row import TradeLogRow, trade_details
from .trade_table_model import TradeTableModel

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel

#: What the filter offers, in order; Spot is long-only, so it has no Short.
_FILTERS = (
    (TradeLogFilter.ALL, "All trades"),
    (TradeLogFilter.LONG, "Long"),
    (TradeLogFilter.SHORT, "Short"),
    (TradeLogFilter.WIN, "Winning trades"),
    (TradeLogFilter.LOSS, "Losing trades"),
)
_EMPTY_TEXT = (
    "No trades to show. Run a backtest (Tools → Run backtest, F7), or widen "
    "the filter and the search."
)
#: How a result the configuration no longer matches reads: dimmed, with the
#: Metrics panel saying why (`BOT-095B`).
_STALE_OPACITY = 0.6


class BackTestTradeLogsPanel(QWidget):  # base-exempt: a dock's content, not a surface
    """The trades of the run on screen."""

    #: `PROP-001` — the selected trade's stable `TradeLogRow.index` (1-based
    #: in the unfiltered list), `-1` when none is selected: the Presenter
    #: draws or clears the chart's entry-exit line.
    selectedTradeChanged = Signal(int)

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("backtestTradesPanel")
        self._vm = view_model
        self.filter = QComboBox()
        self.filter.setObjectName("comboTradeLogFilter")
        self.search = QLineEdit()
        self.search.setObjectName("txtTradeLogSearch")
        self.search.setPlaceholderText("Trade number or date")
        self.search.setClearButtonEnabled(True)
        self.table = SpecTable(
            TradeTableModel(self),
            object_name="tblBacktestTrades",
            empty_text=_EMPTY_TEXT,
            formatter=ZonedValueFormatter(
                lambda: view_model.time_range.displayTimezone
            ),
        )
        self._details = QWidget()
        self._details.setObjectName("backtestTradeDetails")
        self._details_form = QFormLayout(self._details)

        show = QLabel("&Show:")
        show.setBuddy(self.filter)
        find = QLabel("&Find:")
        find.setBuddy(self.search)
        query = QHBoxLayout()
        query.addWidget(show)
        query.addWidget(self.filter)
        query.addWidget(find)
        query.addWidget(self.search, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(query)
        layout.addWidget(self.table.body, 1)
        layout.addWidget(self._details)

        self.filter.currentIndexChanged.connect(self._on_filter_chosen)
        self.search.textEdited.connect(self._on_search_edited)
        #: While the rows are replaced, the selection is put back by hand and
        #: announced once, after.
        self._replacing_rows = False
        self.table.view.selectionModel().selectionChanged.connect(
            lambda *_args: self._on_trade_selection_changed()
        )
        self._wire_view_model()
        self._sync_filters()
        self._sync_search()
        self._sync_rows()
        self._sync_dirty_opacity()

    def _wire_view_model(self) -> None:
        vm = self._vm
        vm.trade_log.filterChanged.connect(self._sync_filters)
        vm.broker_sim.marketChanged.connect(self._sync_filters)
        vm.trade_log.searchTextChanged.connect(self._sync_search)
        vm.trade_log.rowsChanged.connect(self._sync_rows)
        vm.isConfigDirtyChanged.connect(self._sync_dirty_opacity)

    @property
    def selected_trade(self) -> TradeLogRow | None:
        return self.table.selected_row()

    def _sync_filters(self) -> None:
        """EPIC-027D — Spot is long-only: no Short; a chosen Short -> All."""
        spot = self._vm.broker_sim.market == MarketType.SPOT.value
        if spot and self._vm.trade_log.filter == TradeLogFilter.SHORT.value:
            self._vm.trade_log.filter = TradeLogFilter.ALL.value
            return
        offered = [
            (kind, label)
            for kind, label in _FILTERS
            if not (spot and kind is TradeLogFilter.SHORT)
        ]
        self.filter.blockSignals(True)
        self.filter.clear()
        for kind, label in offered:
            self.filter.addItem(label, kind.value)
        self.filter.setCurrentIndex(self.filter.findData(self._vm.trade_log.filter))
        self.filter.blockSignals(False)

    def _on_filter_chosen(self, index: int) -> None:
        value = self.filter.itemData(index)
        if isinstance(value, str):
            self._vm.trade_log.filter = value

    def _sync_search(self) -> None:
        if self.search.text() != self._vm.trade_log.searchText:
            self.search.setText(self._vm.trade_log.searchText)

    def _on_search_edited(self, text: str) -> None:
        self._vm.trade_log.searchText = text

    def _sync_rows(self) -> None:
        """New rows on every query (a filter, a search keystroke, a time zone
        change): the trade the person selected stays selected while it
        still matches, with its chart line and its journal (review of
        PR #356)."""
        kept = self.selected_trade
        self._replacing_rows = True
        try:
            self.table.model.set_rows(self._vm.trade_log.rows)
            if kept is not None:
                self.table.select_first(lambda trade: trade.index == kept.index)
        finally:
            self._replacing_rows = False
        self._show_selected_trade()

    def _on_trade_selection_changed(self) -> None:
        if not self._replacing_rows:
            self._show_selected_trade()

    def _show_selected_trade(self) -> None:
        trade = self.selected_trade
        self._show_details(trade)
        self.selectedTradeChanged.emit(-1 if trade is None else trade.index)

    def _show_details(self, trade: TradeLogRow | None) -> None:
        while self._details_form.rowCount():
            self._details_form.removeRow(0)
        self._details.setVisible(trade is not None)
        if trade is None:
            return
        for label, text in trade_details(trade):
            # A strategy's metadata is text, never an access key.
            self._details_form.addRow(f"{label.replace('&', '&&')}:", QLabel(text))

    def _sync_dirty_opacity(self) -> None:
        # Qt Widgets has no CSS `opacity`; QGraphicsOpacityEffect is the
        # mechanism, built lazily so a panel that never goes stale never
        # pays for one.
        body = self.table.body
        effect = body.graphicsEffect()
        if self._vm.isConfigDirty:
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(body)
                body.setGraphicsEffect(effect)
            effect.setOpacity(_STALE_OPACITY)
        elif effect is not None:
            body.setGraphicsEffect(None)
