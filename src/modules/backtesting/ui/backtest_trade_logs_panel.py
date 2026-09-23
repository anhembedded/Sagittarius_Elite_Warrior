"""The backtest trade-logs panel."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_log_panel import (
    AppLogPanel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    StyleRole,
    Tab,
    TabBar,
    apply_role,
)

from ._drawdown_chart_widget import DrawdownChartWidget
from ._filter_tab_button import _FilterTabButton
from ._monthly_returns_heatmap_widget import MonthlyReturnsHeatmapWidget
from ._trade_log_columns import _COLUMNS
from ._trade_log_row import _TradeLogRowWidget

if TYPE_CHECKING:
    from .backtest_view_model import BackTestViewModel


_FILTER_TABS = [
    ("all", "All"),
    ("long", "Buy (LONG)"),
    ("short", "Sell (SHORT)"),
    ("win", "Winning trades"),
    ("loss", "Losing trades"),
]

_HEADERS = (
    "# / TIME",
    "TYPE",
    "ENTRY PRICE  ➔  EXIT PRICE",
    "SIZE / VOLUME",
    "NET PROFIT / LOSS",
    "RETURN",
)


class BackTestTradeLogsPanel(QWidget):  # base-exempt: screen region, not a card
    """Port of `BackTestTradeLogs.qml`.

    **Not a `Surface`**: it is the bottom region of the screen, holding the
    tab bar, the table and the log panel. The cards are inside it."""

    #: BOT-090's usable-height floor, recomputed in Python instead of read
    #: back from a QML `implicitHeight` property (no QML root exists
    #: anymore) — same constants (`rowHeight`, `minVisibleRows`) the QML
    #: used, so the floor is unchanged.
    ROW_HEIGHT = 44
    MIN_VISIBLE_ROWS = 5

    #: `PROP-001` — emitted with the trade's stable `TradeLogRow.index`
    #: (1-based position in the full, unfiltered trades list) whenever a
    #: row becomes expanded, and with `-1` when that same row collapses
    #: again. The Presenter uses this to draw/clear the chart's
    #: entry-exit connecting line — expand/collapse already means "the
    #: user is looking at this trade", so this reuses that click rather
    #: than adding a second, separate selection gesture.
    selectedTradeChanged = Signal(int)

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._vm = view_model
        self._expanded_rows: dict[int, bool] = {}
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        self._tab_bar = TabBar()
        self._tab_bar.setObjectName("bottomTabBar")
        self._tab_bar.tab_selected.connect(self._on_tab_selected)
        outer.addWidget(self._tab_bar)

        self._trades_tab = self._build_trades_tab()
        outer.addWidget(self._trades_tab, 1)

        self._drawdown_tab = self._build_drawdown_tab()
        outer.addWidget(self._drawdown_tab, 1)

        self._returns_tab = self._build_returns_tab()
        outer.addWidget(self._returns_tab, 1)

        self._log_panel = AppLogPanel("BACKTEST LOG")
        self._log_panel.setObjectName("backtestLogPanel")
        self._log_panel.set_log_model(view_model.log_model)
        outer.addWidget(self._log_panel, 1)

        self._wire_view_model()
        self._sync_all()

    # ------------------------------------------------------------------ #
    # Trades tab
    # ------------------------------------------------------------------ #

    def _build_trades_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("tradeLogsTabContent")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        toolbar = QWidget()
        toolbar.setObjectName("toolbarRow")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(14)

        filters = QWidget()
        filters.setObjectName("tradeLogFilterTabs")
        filters_layout = QHBoxLayout(filters)
        filters_layout.setContentsMargins(0, 0, 0, 0)
        filters_layout.setSpacing(4)
        self._filter_buttons: list[_FilterTabButton] = []
        for value, label in _FILTER_TABS:
            btn = _FilterTabButton(value, label)
            btn.setObjectName(f"tabTradeLogFilter_{value}")
            btn.clicked.connect(lambda _=False, v=value: self._on_filter_clicked(v))
            filters_layout.addWidget(btn)
            self._filter_buttons.append(btn)
        toolbar_layout.addWidget(filters)
        toolbar_layout.addStretch(1)

        self._search_field = QLineEdit()
        self._search_field.setObjectName("txtTradeLogSearch")
        self._search_field.setPlaceholderText("🔍  Search by symbol, date...")
        self._search_field.setFixedSize(200, 28)
        self._search_field.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border: 1px solid {Palette.STATE_HOVER_BG}; border-radius: 6px; "
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; padding: 0 6px;"
        )
        self._search_field.textEdited.connect(self._on_search_edited)
        toolbar_layout.addWidget(self._search_field)

        self._btn_export = QPushButton("Export")
        self._btn_export.setObjectName("btnTradeLogExport")
        self._btn_export.setFixedHeight(28)
        self._btn_export.setIcon(
            get_icon_loader().get_icon("download", Palette.ACCENT, 12)
        )
        self._btn_export.setStyleSheet(
            f"background-color: {Palette.BG_CARD_HEADER}; border: 1px solid {Palette.STATE_NAV_BORDER}; border-radius: 6px; "
            f"color: {Palette.TEXT_PRIMARY}; font-size: 11px; font-weight: bold; padding: 0 10px;"
        )
        self._btn_export.clicked.connect(self._vm.trade_log.request_export)
        toolbar_layout.addWidget(self._btn_export)

        layout.addWidget(toolbar)

        table_container = QFrame()
        apply_role(table_container, StyleRole.SURFACE)
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)

        self._table_header = self._build_table_header()
        table_layout.addWidget(self._table_header)

        self._rows_scroll = QScrollArea()
        self._rows_scroll.setWidgetResizable(True)
        self._rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._rows_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._rows_container = QWidget()
        self._rows_container.setObjectName("listTradeLogRows")
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(0)
        self._rows_layout.addStretch(1)
        self._rows_scroll.setWidget(self._rows_container)
        table_layout.addWidget(self._rows_scroll, 1)

        self._empty_label = QLabel("No trade data yet")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {Palette.MUTED}; font-size: 12px;")
        table_layout.addWidget(self._empty_label)

        self._pagination_row = self._build_pagination_row()
        table_layout.addWidget(self._pagination_row)

        layout.addWidget(table_container, 1)
        return tab

    # ------------------------------------------------------------------ #
    # Drawdown + returns tabs (BOT-106D)
    # ------------------------------------------------------------------ #

    def _build_drawdown_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("drawdownTabContent")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        self._drawdown_chart = DrawdownChartWidget()
        layout.addWidget(self._drawdown_chart, 1)
        return tab

    def _build_returns_tab(self) -> QWidget:
        tab = QWidget()
        tab.setObjectName("returnsTabContent")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        self._returns_heatmap = MonthlyReturnsHeatmapWidget()
        layout.addWidget(self._returns_heatmap, 1)
        return tab

    def _build_table_header(self) -> QWidget:
        header = QFrame()
        header.setFixedHeight(34)
        # Scoped by hand rather than given `TABLE_HEADER`: that role rounds
        # its corners, and this strip sits flush inside a card that already
        # rounds them, with a separator line along its bottom edge instead.
        header.setStyleSheet(
            f"QFrame {{ background-color: {Palette.BG_CARD_HEADER}; "
            f"border-bottom: 1px solid {Palette.BORDER}; }}"
        )
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(8)
        alignments = (
            Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignCenter,
            Qt.AlignmentFlag.AlignLeft,
            Qt.AlignmentFlag.AlignRight,
            Qt.AlignmentFlag.AlignRight,
            Qt.AlignmentFlag.AlignRight,
        )
        for text, stretch, alignment in zip(
            _HEADERS, _COLUMNS, alignments, strict=True
        ):
            label = QLabel(text)
            label.setAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
            label.setStyleSheet(
                f"color: {Palette.MUTED}; font-size: 10px; font-weight: bold; letter-spacing: 0.5px;"
            )
            row.addWidget(label, stretch)
        return header

    def _build_pagination_row(self) -> QWidget:
        row_widget = QWidget()
        row_widget.setFixedHeight(34)
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.addStretch(1)

        self._btn_prev_page = QPushButton("‹  Previous page")
        self._btn_prev_page.setObjectName("btnTradeLogPrevPage")
        self._btn_prev_page.setFixedHeight(26)
        self._btn_prev_page.clicked.connect(
            lambda: setattr(
                self._vm, "tradeLogCurrentPage", self._vm.trade_log.currentPage - 1
            )
        )
        row.addWidget(self._btn_prev_page)

        self._page_label = QLabel()
        self._page_label.setFixedHeight(22)
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet(
            f"background-color: {Palette.STATE_IDLE_BG}; border-radius: 4px; color: {Palette.ACCENT}; "
            f"font-size: 11px; font-weight: bold; padding: 0 8px;"
        )
        row.addWidget(self._page_label)

        self._btn_next_page = QPushButton("Next page  ›")
        self._btn_next_page.setObjectName("btnTradeLogNextPage")
        self._btn_next_page.setFixedHeight(26)
        self._btn_next_page.clicked.connect(
            lambda: setattr(
                self._vm, "tradeLogCurrentPage", self._vm.trade_log.currentPage + 1
            )
        )
        row.addWidget(self._btn_next_page)

        row.addStretch(1)
        return row_widget

    # ------------------------------------------------------------------ #
    # ViewModel wiring
    # ------------------------------------------------------------------ #

    def _wire_view_model(self) -> None:
        vm = self._vm
        vm.activeBottomTabChanged.connect(self._sync_active_tab)
        vm.trade_log.filterChanged.connect(self._sync_filters)
        vm.trade_log.searchTextChanged.connect(self._sync_search)
        vm.trade_log.rowsChanged.connect(self._sync_rows)
        vm.trade_log.rowsChanged.connect(self._sync_tab_badges)
        vm.trade_log.currentPageChanged.connect(self._sync_pagination)
        vm.logModel.countChanged.connect(self._sync_tab_badges)
        vm.isConfigDirtyChanged.connect(self._sync_dirty_opacity)
        vm.run_result.drawdownPointsChanged.connect(self._sync_drawdown)
        vm.run_result.yearlyReturnsChanged.connect(self._sync_returns)

    def _sync_all(self) -> None:
        self._sync_active_tab()
        self._sync_filters()
        self._sync_search()
        self._sync_rows()
        self._sync_tab_badges()
        self._sync_pagination()
        self._sync_dirty_opacity()
        self._sync_drawdown()
        self._sync_returns()

    #: `activeBottomTab` values this panel understands — kept in one place so
    #: an unrecognized value (should never happen; defensive default only)
    #: falls back to "trades" instead of hiding every tab.
    _BOTTOM_TAB_IDS = ("trades", "drawdown", "returns", "logs")

    def _sync_active_tab(self) -> None:
        active = self._vm.activeBottomTab
        if active not in self._BOTTOM_TAB_IDS:
            active = "trades"
        self._trades_tab.setVisible(active == "trades")
        self._drawdown_tab.setVisible(active == "drawdown")
        self._returns_tab.setVisible(active == "returns")
        self._log_panel.setVisible(active == "logs")
        self._tab_bar.set_current_id(active)

    def _on_tab_selected(self, index: int, tab_id: str) -> None:
        self._vm.setActiveBottomTab(tab_id)

    def _sync_tab_badges(self) -> None:
        total = self._vm.trade_log.totalCount
        log_count = self._vm.logModel.rowCount()
        self._tab_bar.set_tabs(
            [
                Tab("trades", "TRADE LIST", f"{total} TRADES"),
                Tab("drawdown", "DRAWDOWN"),
                Tab("returns", "RETURNS"),
                Tab("logs", "BACKTEST LOG", f"{log_count} EVENTS"),
            ]
        )
        self._sync_active_tab()

    def _sync_drawdown(self) -> None:
        self._drawdown_chart.set_points(self._vm.run_result.drawdownPoints)

    def _sync_returns(self) -> None:
        self._returns_heatmap.set_rows(self._vm.run_result.yearlyReturns)

    def _sync_filters(self) -> None:
        current = self._vm.trade_log.filter
        for btn in self._filter_buttons:
            btn.set_active(btn.value == current)

    def _on_filter_clicked(self, value: str) -> None:
        self._vm.trade_log.filter = value

    def _sync_search(self) -> None:
        if self._search_field.text() != self._vm.trade_log.searchText:
            self._search_field.setText(self._vm.trade_log.searchText)

    def _on_search_edited(self, text: str) -> None:
        self._vm.trade_log.searchText = text

    def _sync_rows(self) -> None:
        rows = self._vm.trade_log.rows
        while self._rows_layout.count() > 1:
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        has_rows = bool(rows)
        self._empty_label.setVisible(not has_rows)
        self._rows_scroll.setVisible(has_rows)

        for row_number, row in enumerate(rows):
            index = int(row.get("index", row_number))
            row_widget = _TradeLogRowWidget()
            row_widget.toggled.connect(self._on_row_toggled)
            row_widget.apply_row(index, row, row_number)
            row_widget.set_expanded(self._expanded_rows.get(index, False))
            self._rows_layout.insertWidget(self._rows_layout.count() - 1, row_widget)

    def _on_row_toggled(self, index: int) -> None:
        self._expanded_rows[index] = not self._expanded_rows.get(index, False)
        for i in range(self._rows_layout.count() - 1):
            widget = self._rows_layout.itemAt(i).widget()
            if isinstance(widget, _TradeLogRowWidget) and widget._index == index:
                widget.set_expanded(self._expanded_rows[index])
                break
        self.selectedTradeChanged.emit(index if self._expanded_rows[index] else -1)

    def _sync_pagination(self) -> None:
        vm = self._vm
        visible = vm.trade_log.totalPages > 1
        self._pagination_row.setVisible(visible)
        self._btn_prev_page.setEnabled(vm.trade_log.currentPage > 1)
        self._btn_next_page.setEnabled(
            vm.trade_log.currentPage < vm.trade_log.totalPages
        )
        self._page_label.setText(
            f"Trang {vm.trade_log.currentPage} / {vm.trade_log.totalPages}"
        )

    def _sync_dirty_opacity(self) -> None:
        # Qt Widgets has no CSS `opacity` for arbitrary QFrame content;
        # QGraphicsOpacityEffect is the real mechanism. The *effect object*
        # is still built lazily, below, so a panel that never goes dirty
        # never pays for one -- which is what the laziness was ever for. The
        # import itself is now at the top, where `code-rule.md` requires it:
        # binding a name out of a module PySide6 has already loaded costs
        # nothing, so importing it here bought none of that saving.
        effect = self._trades_tab.graphicsEffect()
        if self._vm.isConfigDirty:
            if not isinstance(effect, QGraphicsOpacityEffect):
                effect = QGraphicsOpacityEffect(self._trades_tab)
                self._trades_tab.setGraphicsEffect(effect)
            effect.setOpacity(0.6)
        elif effect is not None:
            self._trades_tab.setGraphicsEffect(None)

    def minimum_usable_height(self) -> int:
        """Port of `BackTestTradeLogs.qml`'s `minimumUsableHeight` — the
        BOT-090 floor `BackTestView._bind_trade_log_minimum_height()` (or
        its EPIC-006E2 QtWidgets successor) applies via
        `setMinimumHeight()`."""
        return (
            self._tab_bar.sizeHint().height()
            + 10
            + self._table_header.height()
            + self.MIN_VISIBLE_ROWS * self.ROW_HEIGHT
            + self._pagination_row.sizeHint().height()
            + 24
        )
