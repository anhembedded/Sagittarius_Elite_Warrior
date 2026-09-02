from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.app_defaults import (
    FALLBACK_SYMBOL,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.app_log_panel import (
    AppLogPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Card,
    PageShell,
    StyledButton,
    StyleRole,
    apply_role,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.OpenOrdersTable.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.PositionsTable.positions_row import (
    PositionRow,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .trading_widgets import OpenOrdersPanel, PositionsPanel

if TYPE_CHECKING:
    from .trading_view_model import TradingViewModel

_TITLE = "Giao dịch trực tiếp (Testnet)"
_SUBTITLE = "Theo dõi vị thế, lệnh chờ khớp và biểu đồ trực tiếp"
DEFAULT_VIEW_MODEL_CONTEXT_NAME = "viewModel"

_TOGGLE_ON_TEXT = "Tắt giao dịch"
_TOGGLE_OFF_TEXT = "Bật giao dịch"
_TOGGLE_BUSY_TEXT = "Đang xử lý..."


class TradingView(BaseView):
    """
    @brief The View for the Trading screen (`EPIC-021I`) — a `PageShell`
    like every other screen in this app.

    @details Header carries the Enable/Disable toggle; context bar carries
    the chart's symbol picker and the current status line; workspace is
    the live chart above the Positions/Open Orders tables; rail is a
    small session-stats card; console is the standard `AppLogPanel`.

    Wiring mirrors `SettingsView`'s hand-rolled two-way binding: this
    screen has no QML host for its own top-level layout (only the two
    tables are QML islands, via `PositionsPanel`/`OpenOrdersPanel`), so
    `set_view_model()` connects each widget's Qt signal to the matching
    ViewModel slot, and each ViewModel `*Changed` signal back to the
    widget's setter.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: TradingViewModel | None = None
        self.chart = ChartCard(FALLBACK_SYMBOL)
        self._build_ui()

    def set_view_model(
        self,
        view_model: TradingViewModel,
        context_name: str = DEFAULT_VIEW_MODEL_CONTEXT_NAME,
    ) -> None:
        self._view_model = view_model

        self._symbol_combo.blockSignals(True)
        self._apply_symbol_options(view_model.symbolOptions)
        self._apply_symbol(view_model.symbol)
        self._symbol_combo.blockSignals(False)
        self._apply_trading_state(view_model.enabled, view_model.toggleBusy)
        self._apply_status(view_model.statusMessage, view_model.statusIsError)
        self._apply_session_stats(
            view_model.ordersSentThisSession, view_model.openSymbolsCount
        )
        self._log_panel.set_log_model(view_model.log_model)

        self._symbol_combo.currentTextChanged.connect(view_model.requestSymbolChange)
        self._toggle_button.clicked.connect(view_model.requestToggle)

        view_model.symbolOptionsChanged.connect(
            lambda: self._apply_symbol_options(view_model.symbolOptions)
        )
        view_model.symbolChanged.connect(lambda: self._apply_symbol(view_model.symbol))
        view_model.tradingStateChanged.connect(
            lambda: self._apply_trading_state(view_model.enabled, view_model.toggleBusy)
        )
        view_model.statusChanged.connect(
            lambda: self._apply_status(
                view_model.statusMessage, view_model.statusIsError
            )
        )
        view_model.sessionStatsChanged.connect(
            lambda: self._apply_session_stats(
                view_model.ordersSentThisSession, view_model.openSymbolsCount
            )
        )

    def set_positions(self, rows: list[PositionRow]) -> None:
        self._positions_panel.set_rows(rows)

    def set_open_orders(self, rows: list[OpenOrderRow]) -> None:
        self._open_orders_panel.set_rows(rows)

    # ------------------------------------------------------------------ #
    # Widget <-> ViewModel apply helpers (the "Python writes, UI shows" half)
    # ------------------------------------------------------------------ #

    def _apply_symbol_options(self, options: list[str]) -> None:
        current = self._symbol_combo.currentText()
        self._symbol_combo.blockSignals(True)
        self._symbol_combo.clear()
        self._symbol_combo.addItems(options)
        if current in options:
            self._symbol_combo.setCurrentText(current)
        self._symbol_combo.blockSignals(False)

    def _apply_symbol(self, symbol: str) -> None:
        if symbol and self._symbol_combo.currentText() != symbol:
            self._symbol_combo.blockSignals(True)
            self._symbol_combo.setCurrentText(symbol)
            self._symbol_combo.blockSignals(False)

    def _apply_trading_state(self, enabled: bool, busy: bool) -> None:
        self._toggle_button.setEnabled(not busy)
        if busy:
            self._toggle_button.setText(_TOGGLE_BUSY_TEXT)
        else:
            self._toggle_button.setText(
                _TOGGLE_ON_TEXT if enabled else _TOGGLE_OFF_TEXT
            )
        self._connection_dot.setStyleSheet(
            f"color: {Palette.SUCCESS if enabled else Palette.MUTED}; font-size: 14px;"
        )
        self._connection_label.setText(
            "Trading đang BẬT" if enabled else "Trading đang TẮT"
        )

    def _apply_status(self, message: str, is_error: bool) -> None:
        self._status_label.setText(message)
        color = Palette.DANGER if is_error else Palette.MUTED
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _apply_session_stats(self, orders_sent: int, open_symbols_count: int) -> None:
        self._orders_sent_value.setText(str(orders_sent))
        self._open_symbols_value.setText(str(open_symbols_count))

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        apply_role(label, StyleRole.BODY_LABEL)
        return label

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet(
            f"{type(self).__name__} {{ background-color: {Palette.BG}; }}"
        )

        self._shell = PageShell()
        outer.addWidget(self._shell)

        self._toggle_button = StyledButton(
            _TOGGLE_OFF_TEXT, role=StyleRole.PRIMARY_BUTTON
        )
        self._toggle_button.setObjectName("btnToggleTrading")
        self._toggle_button.setFixedHeight(32)
        self._toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)

        self._shell.set_header(
            _TITLE,
            _SUBTITLE,
            icon=get_icon_loader().get_icon("chart-candlestick", Palette.ACCENT),
            actions=self._toggle_button,
        )

        self._shell.set_context_bar(self._build_context_bar())
        self._shell.set_workspace(self._build_workspace(), rail=self._build_rail())

        self._log_panel = AppLogPanel("NHẬT KÝ GIAO DỊCH")
        self._shell.set_console(self._log_panel)

    def _build_context_bar(self) -> QWidget:
        bar = QWidget()
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)

        row.addWidget(self._field_label("Symbol:"))
        self._symbol_combo = QComboBox()
        self._symbol_combo.setObjectName("cboTradingSymbol")
        self._symbol_combo.setMinimumWidth(140)
        row.addWidget(self._symbol_combo)

        row.addSpacing(16)
        self._connection_dot = QLabel("●")
        self._connection_dot.setObjectName("lblConnectionDot")
        row.addWidget(self._connection_dot)
        self._connection_label = QLabel()
        self._connection_label.setObjectName("lblConnectionState")
        row.addWidget(self._connection_label)

        row.addSpacing(16)
        self._status_label = QLabel()
        self._status_label.setObjectName("lblTradingStatus")
        self._status_label.setWordWrap(True)
        row.addWidget(self._status_label, 1)

        return bar

    def _build_workspace(self) -> QWidget:
        workspace = QWidget()
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.chart, 2)

        tables_row = QWidget()
        tables_layout = QHBoxLayout(tables_row)
        tables_layout.setContentsMargins(0, 0, 0, 0)
        tables_layout.setSpacing(12)

        self._positions_panel = PositionsPanel()
        self._positions_panel.setObjectName("positionsPanel")
        self._open_orders_panel = OpenOrdersPanel()
        self._open_orders_panel.setObjectName("openOrdersPanel")
        tables_layout.addWidget(self._positions_panel, 1)
        tables_layout.addWidget(self._open_orders_panel, 1)

        layout.addWidget(tables_row, 1)
        return workspace

    def _build_rail(self) -> QWidget:
        card = Card("PHIÊN GIAO DỊCH")
        card.setObjectName("tradingSessionRail")
        card.body_layout.setContentsMargins(12, 12, 12, 12)
        card.body_layout.setSpacing(10)

        card.body_layout.addWidget(self._field_label("Số lệnh đã gửi phiên này"))
        self._orders_sent_value = QLabel("0")
        self._orders_sent_value.setObjectName("lblOrdersSentThisSession")
        apply_role(self._orders_sent_value, StyleRole.STAT_VALUE)
        card.body_layout.addWidget(self._orders_sent_value)

        card.body_layout.addWidget(self._field_label("Số symbol đang có vị thế mở"))
        self._open_symbols_value = QLabel("0")
        self._open_symbols_value.setObjectName("lblOpenSymbolsCount")
        apply_role(self._open_symbols_value, StyleRole.STAT_VALUE)
        card.body_layout.addWidget(self._open_symbols_value)

        card.body_layout.addStretch(1)
        return card
