from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.live_strategy_config import (
    MAX_LEVERAGE,
    MAX_SIZING_PERCENT,
    MIN_LEVERAGE,
    MIN_SIZING_PERCENT,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_order_row import (
    OpenOrderRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.open_orders_panel import (
    OpenOrdersPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.position_row import (
    PositionRow,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.order_book.positions_panel import (
    PositionsPanel,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import (
    ChartCard,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    FALLBACK_SYMBOL,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_log_panel import (
    AppLogPanel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import (
    Palette,
    get_icon_loader,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import (
    Card,
    PageShell,
    StyledButton,
    StyleRole,
    apply_role,
)
from sagittarius_engine.extensions.pyside_mvc import BaseView

if TYPE_CHECKING:
    from .trading_view_model import TradingViewModel

_TITLE = "Live Trading (Testnet)"
_SUBTITLE = "Monitor positions, pending orders, and the live chart"
DEFAULT_VIEW_MODEL_CONTEXT_NAME = "viewModel"

_TOGGLE_ON_TEXT = "Disable Trading"
_TOGGLE_OFF_TEXT = "Enable Trading"
_TOGGLE_BUSY_TEXT = "Processing..."

#: `EPIC-021M` — the equity chart's `ChartCard(symbol=...)` title; not a
#: real trading symbol, just what `Card`'s header shows.
_EQUITY_CHART_TITLE = "Equity"

#: An empty `ChartCard`'s own `sizeHint()` is tiny (no candles/toolbar to
#: size around) — `_build_workspace()`'s stretch factors only split space
#: *beyond* each widget's own minimum, so a near-zero minimum here left
#: the equity chart squeezed to a sliver rather than sharing fairly in the
#: split (same defect user-reported and fixed on `DashboardView`'s mirror
#: of this exact construction). This floor gives it a legible baseline;
#: `PageShell.set_workspace()` already wraps the whole workspace in a
#: `PreferredHeightScrollArea` (`kit/page_shell.py`), so if this floor plus
#: everything else no longer fits the viewport, the page scrolls instead of
#: compressing this chart back down.
_EQUITY_CHART_MINIMUM_HEIGHT = 220

# --- `EPIC-022D` strategy card ---------------------------------------- #
#: Domain terminology fixed by `ui-presentation-rule.md`: strategy
#: parameters are "Thông số Chiến lược", never the general Bot settings.
_PARAMS_BUTTON_TEXT = "Strategy Parameters…"
_ARM_TEXT = "Arm Strategy"
_DISARM_TEXT = "Disarm"
_NOT_ARMED_TEXT = "No strategy armed."
_NO_SIGNAL_TEXT = "No signal yet."
#: The spin-box ranges come from `LiveStrategyConfig`'s own bounds, not
#: from literals typed here (`BOT-125` review). A widget can only constrain
#: what is typed into it; these values also arrive from `app_config.json`
#: at boot and from a restored session, so the value object is where the
#: rule has to live — this just keeps the widget from offering something
#: the domain would reject.


class TradingView(BaseView):
    """
    @brief The View for the Trading screen (`EPIC-021I`) — a `PageShell`
    like every other screen in this app.

    @details Header carries the Enable/Disable toggle; context bar carries
    the chart's symbol picker, the current status line, and the
    "DỪNG KHẨN CẤP" Emergency Stop button (`EPIC-021K`); workspace is
    the live price chart, the Positions/Open Orders tables, and the live
    equity chart (`EPIC-021M`), stacked top to bottom; rail is a small
    session-stats card; console is the standard `AppLogPanel`.

    Wiring mirrors `SettingsView`'s hand-rolled two-way binding: this
    screen has no QML host for its own top-level layout (only the two
    tables are QML islands, via `PositionsPanel`/`OpenOrdersPanel`), so
    `set_view_model()` connects each widget's Qt signal to the matching
    ViewModel slot, and each ViewModel `*Changed` signal back to the
    widget's setter.
    """

    #: `EPIC-024B` §0 — re-exposes `OpenOrdersPanel.cancelRequested`, same
    #: layered re-export `DashboardView` does for its own identical panel.
    cancelOrderRequested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model: TradingViewModel | None = None
        self.chart = ChartCard(FALLBACK_SYMBOL)
        self.equity_chart = self._build_equity_chart()
        self._build_ui()

    def _build_equity_chart(self) -> ChartCard:
        """`EPIC-021M` §3 — a dedicated `ChartCard`, not a second mode on
        `self.chart`: equity is account-level, not per-symbol, and the
        two vary independently (switching the price chart's symbol must
        never touch this one). The candle toolbar (timeframe picker) and
        volume pane are meaningless for a series with no OHLC/volume of
        its own — hidden rather than removed, so this stays a plain,
        unmodified `ChartCard` (`EPIC-021M` §2.4's "dùng ChartCard").
        """
        card = ChartCard(_EQUITY_CHART_TITLE)
        card.set_chart_type("line")
        card.set_volume_visible(False)
        card.toolbar.setVisible(False)
        card.setMinimumHeight(_EQUITY_CHART_MINIMUM_HEIGHT)
        return card

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
        self._emergency_stop_button.clicked.connect(view_model.requestEmergencyStop)

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

        # --- `EPIC-022D` strategy card --------------------------------- #
        self._apply_strategy_options(
            view_model.strategyOptions, view_model.intervalOptions
        )
        self._apply_strategy_selection(view_model)
        self._apply_armed_summary(
            view_model.armedSummary, view_model.strategyBusy, view_model.enabled
        )
        self._apply_last_signal(view_model.lastSignalText)

        self._strategy_combo.currentIndexChanged.connect(
            lambda _index: view_model.requestStrategySelection(
                self._strategy_combo.currentData() or ""
            )
        )
        self._interval_combo.currentTextChanged.connect(
            view_model.requestIntervalSelection
        )
        self._sizing_spin.valueChanged.connect(view_model.requestSizingPercent)
        self._leverage_spin.valueChanged.connect(view_model.requestLeverage)
        self._arm_button.clicked.connect(view_model.requestArm)
        self._disarm_button.clicked.connect(view_model.requestDisarm)
        self._params_button.clicked.connect(self._open_strategy_params_dialog)

        view_model.strategyConfigChanged.connect(
            lambda: self._on_strategy_config_changed(view_model)
        )
        # The card is also disabled by trading turning on, which arrives on
        # `tradingStateChanged`, not on `strategyConfigChanged`.
        view_model.tradingStateChanged.connect(
            lambda: self._apply_armed_summary(
                view_model.armedSummary, view_model.strategyBusy, view_model.enabled
            )
        )
        view_model.lastSignalChanged.connect(
            lambda: self._apply_last_signal(view_model.lastSignalText)
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
        self._connection_label.setText("Trading is ON" if enabled else "Trading is OFF")

    def _apply_status(self, message: str, is_error: bool) -> None:
        self._status_label.setText(message)
        color = Palette.DANGER if is_error else Palette.MUTED
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _apply_session_stats(self, orders_sent: int, open_symbols_count: int) -> None:
        self._orders_sent_value.setText(str(orders_sent))
        self._open_symbols_value.setText(str(open_symbols_count))

    # --- `EPIC-022D` strategy card ------------------------------------- #

    def _on_strategy_config_changed(self, view_model: TradingViewModel) -> None:
        self._apply_strategy_options(
            view_model.strategyOptions, view_model.intervalOptions
        )
        self._apply_strategy_selection(view_model)
        self._apply_armed_summary(
            view_model.armedSummary, view_model.strategyBusy, view_model.enabled
        )

    def _apply_strategy_options(
        self, options: list[dict], interval_options: list[str]
    ) -> None:
        """@details Each row's registry key rides on `setItemData`, never
        on the visible text: the label is humanised for reading
        ("Ema Crossover") while `ArmStrategyCommand` needs the exact key
        (`ema_crossover`). Deriving one from the other by string surgery
        is how a renamed strategy silently stops being armable."""
        self._strategy_combo.blockSignals(True)
        self._strategy_combo.clear()
        for option in options:
            self._strategy_combo.addItem(option.get("label", ""), option.get("key", ""))
        self._strategy_combo.blockSignals(False)

        self._interval_combo.blockSignals(True)
        self._interval_combo.clear()
        self._interval_combo.addItems(interval_options)
        self._interval_combo.blockSignals(False)

    def _apply_strategy_selection(self, view_model: TradingViewModel) -> None:
        self._strategy_combo.blockSignals(True)
        index = self._strategy_combo.findData(view_model.selectedStrategyKey)
        if index >= 0:
            self._strategy_combo.setCurrentIndex(index)
        self._strategy_combo.blockSignals(False)

        self._interval_combo.blockSignals(True)
        if view_model.liveInterval:
            self._interval_combo.setCurrentText(view_model.liveInterval)
        self._interval_combo.blockSignals(False)

        for spin, value in (
            (self._sizing_spin, view_model.sizingPercent),
            (self._leverage_spin, view_model.leverage),
        ):
            spin.blockSignals(True)
            spin.setValue(value)
            spin.blockSignals(False)

    def _apply_armed_summary(
        self, summary: str, busy: bool, trading_enabled: bool
    ) -> None:
        self._armed_label.setText(summary or _NOT_ARMED_TEXT)
        self._armed_label.setStyleSheet(
            f"color: {Palette.SUCCESS if summary else Palette.MUTED}; font-size: 11px;"
        )
        # `EPIC-022` §4.1 — swapping the engine under an open position is
        # refused by the command handler too; this is the same rule made
        # visible before the click rather than after it.
        editable = not busy and not trading_enabled
        for widget in self._strategy_controls:
            widget.setEnabled(editable)

    def _apply_last_signal(self, text: str) -> None:
        self._last_signal_label.setText(text or _NO_SIGNAL_TEXT)

    def _open_strategy_params_dialog(self) -> None:
        """@details Built fresh per opening rather than kept alive: the
        form's fields are rebuilt from the schema of whichever strategy is
        currently picked, and a retained dialog would have to be told to
        forget the previous strategy's widgets anyway. Imported lazily —
        the dialog pulls in `QScrollArea`/`Overlay` chrome no user who
        never opens it should pay for at screen construction."""
        if self._view_model is None:
            return
        from Sagittarius_Elite_Warrior.src.presentation.ui.components.strategy_params.strategy_params_dialog import (
            StrategyParamsDialog,
        )

        dialog = StrategyParamsDialog(self._view_model, self)
        dialog.exec()

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

        self._log_panel = AppLogPanel("TRADING LOG")
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

        self._emergency_stop_button = StyledButton(
            "EMERGENCY STOP", role=StyleRole.DANGER_BUTTON
        )
        self._emergency_stop_button.setObjectName("btnEmergencyStop")
        self._emergency_stop_button.setFixedHeight(32)
        self._emergency_stop_button.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self._emergency_stop_button)

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
        self._open_orders_panel.cancelRequested.connect(self.cancelOrderRequested)
        tables_layout.addWidget(self._positions_panel, 1)
        tables_layout.addWidget(self._open_orders_panel, 1)

        layout.addWidget(tables_row, 1)
        layout.addWidget(self.equity_chart, 1)
        return workspace

    def _build_rail(self) -> QWidget:
        """`EPIC-022D` — the rail became a column of cards rather than one
        card: strategy configuration, the latest signal, then the session
        counters. Ordered by how often a user acts on them, not by when
        they were built."""
        rail = QWidget()
        column = QVBoxLayout(rail)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(12)
        column.addWidget(self._build_strategy_card())
        column.addWidget(self._build_last_signal_card())
        column.addWidget(self._build_session_card())
        column.addStretch(1)
        return rail

    def _build_strategy_card(self) -> QWidget:
        card = Card("STRATEGY")
        card.setObjectName("tradingStrategyCard")
        card.body_layout.setContentsMargins(12, 12, 12, 12)
        card.body_layout.setSpacing(8)

        card.body_layout.addWidget(self._field_label("Strategy"))
        self._strategy_combo = QComboBox()
        self._strategy_combo.setObjectName("cboLiveStrategy")
        card.body_layout.addWidget(self._strategy_combo)

        card.body_layout.addWidget(self._field_label("Trading Timeframe"))
        self._interval_combo = QComboBox()
        self._interval_combo.setObjectName("cboLiveInterval")
        card.body_layout.addWidget(self._interval_combo)

        card.body_layout.addWidget(self._field_label("% Capital per Trade"))
        self._sizing_spin = QDoubleSpinBox()
        self._sizing_spin.setObjectName("spnLiveSizingPercent")
        self._sizing_spin.setRange(MIN_SIZING_PERCENT, MAX_SIZING_PERCENT)
        self._sizing_spin.setSingleStep(1.0)
        self._sizing_spin.setSuffix(" %")
        card.body_layout.addWidget(self._sizing_spin)

        card.body_layout.addWidget(self._field_label("Leverage"))
        self._leverage_spin = QDoubleSpinBox()
        self._leverage_spin.setObjectName("spnLiveLeverage")
        self._leverage_spin.setRange(MIN_LEVERAGE, MAX_LEVERAGE)
        self._leverage_spin.setSingleStep(1.0)
        self._leverage_spin.setSuffix(" x")
        card.body_layout.addWidget(self._leverage_spin)

        self._params_button = StyledButton(
            _PARAMS_BUTTON_TEXT, role=StyleRole.SECONDARY_BUTTON
        )
        self._params_button.setObjectName("btnStrategyParams")
        self._params_button.setCursor(Qt.CursorShape.PointingHandCursor)
        card.body_layout.addWidget(self._params_button)

        actions = QWidget()
        actions_row = QHBoxLayout(actions)
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        self._arm_button = StyledButton(_ARM_TEXT, role=StyleRole.PRIMARY_BUTTON)
        self._arm_button.setObjectName("btnArmStrategy")
        self._arm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._disarm_button = StyledButton(
            _DISARM_TEXT, role=StyleRole.SECONDARY_BUTTON
        )
        self._disarm_button.setObjectName("btnDisarmStrategy")
        self._disarm_button.setCursor(Qt.CursorShape.PointingHandCursor)
        actions_row.addWidget(self._arm_button, 1)
        actions_row.addWidget(self._disarm_button, 1)
        card.body_layout.addWidget(actions)

        self._armed_label = QLabel(_NOT_ARMED_TEXT)
        self._armed_label.setObjectName("lblArmedStrategy")
        self._armed_label.setWordWrap(True)
        card.body_layout.addWidget(self._armed_label)

        #: Everything above is disabled while trading is on. The command
        #: handlers refuse a swap anyway (`EPIC-022` §4.1) — this is the
        #: half of that rule the user can see before clicking, rather
        #: than a refusal after.
        self._strategy_controls = (
            self._strategy_combo,
            self._interval_combo,
            self._sizing_spin,
            self._leverage_spin,
            self._params_button,
            self._arm_button,
            self._disarm_button,
        )
        return card

    def _build_last_signal_card(self) -> QWidget:
        card = Card("LATEST SIGNAL")
        card.setObjectName("tradingLastSignalCard")
        card.body_layout.setContentsMargins(12, 12, 12, 12)
        card.body_layout.setSpacing(6)
        self._last_signal_label = QLabel(_NO_SIGNAL_TEXT)
        self._last_signal_label.setObjectName("lblLastSignal")
        self._last_signal_label.setWordWrap(True)
        card.body_layout.addWidget(self._last_signal_label)
        return card

    def _build_session_card(self) -> QWidget:
        card = Card("TRADING SESSION")
        card.setObjectName("tradingSessionRail")
        card.body_layout.setContentsMargins(12, 12, 12, 12)
        card.body_layout.setSpacing(10)

        card.body_layout.addWidget(self._field_label("Orders Sent This Session"))
        self._orders_sent_value = QLabel("0")
        self._orders_sent_value.setObjectName("lblOrdersSentThisSession")
        apply_role(self._orders_sent_value, StyleRole.STAT_VALUE)
        card.body_layout.addWidget(self._orders_sent_value)

        card.body_layout.addWidget(self._field_label("Symbols With Open Positions"))
        self._open_symbols_value = QLabel("0")
        self._open_symbols_value.setObjectName("lblOpenSymbolsCount")
        apply_role(self._open_symbols_value, StyleRole.STAT_VALUE)
        card.body_layout.addWidget(self._open_symbols_value)
        return card
