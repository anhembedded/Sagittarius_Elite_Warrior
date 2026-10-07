"""The Market mode's view (`EPIC-033H`), laid out as HLD §11.2.1 lists it.

- **Central:** the charts, one tab per open symbol; an instruction while
  none is open.
- **Right, tabbed:** the Watchlist (a table from its column specs) and the
  Indicators (a checklist of the scripts the registry knows).
- **Bottom:** the window's one Output pane, which shows this mode's channel.
- **Status bar:** the exchange connection and the market data stream, each a
  word, shown in every mode (`IStatusSource`).

Stock controls in a `WorkbenchSurface`, no style sheet; the view only shows
and reports what the user does (the presenter decides).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDockWidget,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.indicators.ui.script_params_sink import (
    IndicatorScriptParamsSink,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.empty_page import empty_page
from Sagittarius_Elite_Warrior.src.support.ui_kit.output_source_view import (
    OutputSourceView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.param_form import (
    StrategyParamsDialog,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.plain_label import plain_label
from Sagittarius_Elite_Warrior.src.support.ui_kit.spec_table import SpecTable
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc import LogListModel
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import (
    OutputChannel,
)

from .chart_history import HistoryRange
from .history_range_dialog import HistoryRangeDialog
from .watchlist_table_model import WatchlistRow, WatchlistTableModel

#: This mode's surface. Declared here because a module may not import
#: `shell/`; `test_market_view.py` holds it equal to `shell/surfaces.py`'s
#: `market` entry, as the Bots view's is.
MARKET_SURFACE = Surface(
    "market", owner="trading", accepts=frozenset({Place.WORKSPACE, Place.RAIL})
)

_NO_CHART_TEXT = (
    "No chart is open. Open one from the Watchlist: double-click a symbol, "
    "or select it and press Enter."
)
_NO_SYMBOLS_TEXT = "No symbols are tracked. Choose them in Tools → Options."


@dataclass(frozen=True)
class IndicatorChoice:
    """One script of the Indicators checklist."""

    key: str
    title: str
    checked: bool


class MarketView(OutputSourceView):
    """@brief The charts beside the Watchlist and the Indicators."""

    #: The user asked to open (or bring forward) a symbol's chart.
    symbol_opened = Signal(str)
    #: The user closed a symbol's chart.
    chart_closed = Signal(str)
    #: The chart in front changed; `""` when none is open.
    current_chart_changed = Signal(str)
    #: The checked indicators, in list order (a tuple of keys).
    indicators_changed = Signal(tuple)
    #: The script selected in the Indicators panel changed (its key, `""`
    #: for none): what Tools → Indicator parameters… edits.
    indicator_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log = LogListModel(self)
        self._output = OutputChannel("market", "Market", self.log)
        self.watchlist = WatchlistTableModel(self)
        # By symbol, the order a user finds a symbol in (`EPIC-033N`).
        self._watchlist = SpecTable(
            self.watchlist, object_name="tblWatchlist", empty_text=_NO_SYMBOLS_TEXT
        )
        self._watchlist.sort_by(WatchlistTableModel.column("symbol"))
        self.indicators = QListWidget()
        self.indicators.setObjectName("lstIndicators")
        self.tabs = QTabWidget()
        self.tabs.setObjectName("tabMarketCharts")
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self._no_chart = empty_page(_NO_CHART_TEXT, "lblNoChart")
        self._central = QStackedWidget()
        self._central.addWidget(self._no_chart)
        self._central.addWidget(self.tabs)
        self.connection = plain_label()
        self.connection.setObjectName("lblConnection")
        self.stream = plain_label()
        self.stream.setObjectName("lblMarketStream")
        self._charts: dict[str, ChartCard] = {}
        self._surface = WorkbenchSurface(MARKET_SURFACE)
        self._surface.place_widget(Place.WORKSPACE, self._central)
        self._surface.place_widget(Place.RAIL, self._watchlist.body, title="Watchlist")
        self._surface.place_widget(Place.RAIL, self.indicators, title="Indicators")
        # Tabbed docks show the last one added; the Watchlist is what the
        # mode is opened for, so it is the one in front.
        self._watchlist_dock = self._dock_holding(self._watchlist.body)
        self._watchlist_dock.raise_()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._surface)
        self._connect()

    # -- IStatusSource ------------------------------------------------------

    def status_widgets(self) -> Sequence[QWidget]:
        return (self.connection, self.stream)

    # -- what the presenter shows ---------------------------------------------

    @property
    def open_symbols(self) -> tuple[str, ...]:
        """The open charts, in tab order."""
        return tuple(self._symbol_at(i) for i in range(self.tabs.count()))

    @property
    def selected_indicator(self) -> str:
        """The key of the script selected in the Indicators panel, `""` for
        none."""
        item = self.indicators.currentItem()
        return "" if item is None else str(item.data(Qt.ItemDataRole.UserRole))

    @property
    def current_symbol(self) -> str:
        return self._symbol_at(self.tabs.currentIndex())

    def add_chart(self, symbol: str, chart: ChartCard) -> None:
        """Adds `symbol`'s chart as the last tab and brings it forward."""
        self._charts[symbol] = chart
        self.tabs.setCurrentIndex(self.tabs.addTab(chart, symbol))
        self._central.setCurrentWidget(self.tabs)

    def show_chart(self, symbol: str) -> None:
        chart = self._charts.get(symbol)
        if chart is not None:
            self.tabs.setCurrentWidget(chart)

    def remove_chart(self, symbol: str) -> None:
        chart = self._charts.pop(symbol, None)
        if chart is None:
            return
        self.tabs.removeTab(self.tabs.indexOf(chart))
        chart.deleteLater()
        if not self._charts:
            self._central.setCurrentWidget(self._no_chart)

    def set_indicator_choices(self, choices: Sequence[IndicatorChoice]) -> None:
        """Fills the checklist without reporting it as the user's choice;
        the selection the refill dropped is reported, so a command acting
        on the selected script never stays on for a script no longer
        selected."""
        self.indicators.blockSignals(True)
        self.indicators.clear()
        for choice in choices:
            item = QListWidgetItem(choice.title)
            item.setData(Qt.ItemDataRole.UserRole, choice.key)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                Qt.CheckState.Checked if choice.checked else Qt.CheckState.Unchecked
            )
            self.indicators.addItem(item)
        self.indicators.blockSignals(False)
        self.indicator_selected.emit(self.selected_indicator)

    def set_connection_text(self, text: str) -> None:
        self.connection.setText(text)

    def set_stream_text(self, text: str) -> None:
        self.stream.setText(text)

    def ask_history_range(
        self, symbol: str, proposed: HistoryRange
    ) -> HistoryRange | None:
        """View → Load range…: the span the user chose, `None` on Cancel."""
        dialog = HistoryRangeDialog(symbol, proposed, self)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return None
            return dialog.choice()
        finally:
            dialog.deleteLater()

    def edit_indicator_params(self, sink: IndicatorScriptParamsSink) -> None:
        """Tools → Indicator parameters…: the Dev Board's dialog (`BOT-063`),
        modal over the window; returns once it closes."""
        dialog = StrategyParamsDialog(sink, self.window(), title="Indicator Parameters")
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    # -- what the user does ---------------------------------------------------

    def _connect(self) -> None:
        self._watchlist.view.activated.connect(self._on_watchlist_activated)
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.currentChanged.connect(
            lambda _index: self.current_chart_changed.emit(self.current_symbol)
        )
        self.indicators.itemChanged.connect(self._on_indicator_changed)
        self.indicators.currentItemChanged.connect(
            lambda _current, _previous: self.indicator_selected.emit(
                self.selected_indicator
            )
        )

    def _on_watchlist_activated(self, index: QModelIndex) -> None:
        row: WatchlistRow | None = self._watchlist.row_at(index)
        if row is not None:
            self.symbol_opened.emit(row.symbol)

    def _on_tab_close_requested(self, index: int) -> None:
        self.chart_closed.emit(self._symbol_at(index))

    def _dock_holding(self, widget: QWidget) -> QDockWidget:
        for dock in self._surface.findChildren(QDockWidget):
            if dock.widget() is widget:
                return dock
        raise LookupError("the surface placed no dock for this widget")

    def _symbol_at(self, index: int) -> str:
        """The symbol of tab `index` (`""` for none), read from the chart it
        holds: a tab's text is the style's to decorate (an access key)."""
        widget = self.tabs.widget(index)
        for symbol, chart in self._charts.items():
            if chart is widget:
                return symbol
        return ""

    def _on_indicator_changed(self, _item: QListWidgetItem) -> None:
        checked = []
        for row in range(self.indicators.count()):
            item = self.indicators.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                checked.append(str(item.data(Qt.ItemDataRole.UserRole)))
        self.indicators_changed.emit(tuple(checked))
