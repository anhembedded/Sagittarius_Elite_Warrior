from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from sagittarius_engine.extensions.pyside_mvc import BaseView, create_quick_widget

from .chart_canvas_view import (
    ChartDisplayMode,
    equity_curve_to_candles,
    equity_curve_to_line_data,
    trade_flag_markers,
)
from .chart_controls import BacktestChartControls

_QML_DIR = Path(__file__).parent
_TOP_PANEL_QML = "BackTestTopPanel.qml"
_TRADE_LOGS_QML = "BackTestTradeLogs.qml"

#: Toolbar row (~40px) + metrics header row (~24px) + the MetricCard row
#: itself (MetricCard.qml's own implicitHeight: 75) + ColumnLayout's 2x10px
#: margins + 2x10px inter-row spacing — 120 (BOT-022's original budget, sized
#: for a single plain result-text line, before BOT-055's real stat cards
#: existed) clipped the cards' value/badge row off entirely.
_TOP_PANEL_HEIGHT = 190

_EQUITY_SUBPLOT_KEY = "equity"
_EQUITY_SUBPLOT_COLOR = (
    "#f0b90b"  # Theme.accent's hex — chart_card has no Qt theme singleton access
)
_TRADE_FLAGS_KEY = "backtest_trades"


class BackTestView(BaseView):
    """
    @brief View for the Backtest Screen, using a hybrid QSplitter layout:
    a fixed-height top toolbar/metrics panel (QML), a chart area (QtWidgets
    `ChartCard`, matching the Dev Board's hybrid approach), and a bottom
    trade-logs panel (QML).

    @details
    Two `QQuickWidget`s share one `viewModel` context property — set once via
    `set_view_model()` — rather than one `QmlHostView` per the framework's
    single-document convention, because this screen genuinely needs 2 QML
    documents at once (BOT-022 §2 layout) plus a native chart widget between
    them. Ordering contract mirrors `QmlHostView` exactly: the Presenter
    calls `set_view_model()` before `load_qml()`, so both QML documents parse
    against a view model that already holds real values.

    Chart rendering (BOT-056) is native, driven by `on_backtest_data_ready()`
    plus the mode/toggle setters below — kept out of QML/ViewModel entirely
    (see `BacktestChartControls`'s own docstring for why) and out of
    `ChartCard`'s own core: this class only ever calls `ChartCard`'s already
    public API, never touches its internals.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_model = None
        self.chart_cards: list = []
        self.chart_controls: BacktestChartControls | None = None
        self._chart_mode = ChartDisplayMode.OHLC
        self._equity_subplot_added = False
        self._last_result = None
        self._last_klines: list = []
        self._last_volume: list = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(10)

        self.top_widget = create_quick_widget()
        self.top_widget.setFixedHeight(_TOP_PANEL_HEIGHT)
        outer_layout.addWidget(self.top_widget)

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        outer_layout.addWidget(main_splitter, 1)

        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(0)
        main_splitter.addWidget(self.charts_container)

        self.bottom_widget = create_quick_widget()
        main_splitter.addWidget(self.bottom_widget)

        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setSizes([600, 200])

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers the screen's ViewModel as a QML context property on
        BOTH quick widgets. Must be called before load_qml() — see the
        ordering contract in this class's docstring."""
        self._view_model = view_model
        self.top_widget.rootContext().setContextProperty(context_name, view_model)
        self.bottom_widget.rootContext().setContextProperty(context_name, view_model)

    def load_qml(self) -> None:
        """Loads this screen's fixed pair of QML documents."""
        self.top_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / _TOP_PANEL_QML)))
        self.bottom_widget.setSource(
            QUrl.fromLocalFile(str(_QML_DIR / _TRADE_LOGS_QML))
        )

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """Receives FSM state changes from BasePresenter and forwards them to
        the ViewModel's `uiMode` property — same duck-typed hook
        `QmlHostView.apply_ui_mode` provides for single-document screens."""
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))

    def render_symbol_cards(self, symbols: list[str]) -> list:
        for i in reversed(range(self.charts_layout.count())):
            item = self.charts_layout.itemAt(i)
            widget = item.widget()
            if widget:
                if hasattr(widget, "cleanup"):
                    widget.cleanup()
                self.charts_layout.removeItem(item)
                widget.deleteLater()

        self.chart_cards = []
        self.chart_controls = None
        for symbol in symbols:
            from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card import (
                ChartCard,
            )

            card = ChartCard(symbol)
            self.chart_cards.append(card)
            self.charts_layout.addWidget(card, 1)

        if self.chart_cards:
            self.chart_controls = BacktestChartControls()
            self.chart_cards[0].add_to_header(self.chart_controls)

        return self.chart_cards

    # ------------------------------------------------------------------ #
    # Chart rendering (BOT-056) — driven by BackTestPresenter
    # ------------------------------------------------------------------ #

    def on_backtest_data_ready(self, result, klines: list, volume: list) -> None:
        """Caches the latest run's data and (re-)renders it under whichever
        mode/toggles are currently selected."""
        self._last_result = result
        self._last_klines = klines
        self._last_volume = volume
        self._render_chart()

    def set_chart_mode(self, mode: ChartDisplayMode) -> None:
        self._chart_mode = mode
        if self._last_result is not None:
            self._render_chart()

    def set_volume_visible(self, visible: bool) -> None:
        card = self._current_card()
        if card is not None:
            card.set_volume_visible(visible)

    def set_trade_flags_visible(self, visible: bool) -> None:
        card = self._current_card()
        if card is None or self._last_result is None:
            return
        if visible and self._chart_mode is not ChartDisplayMode.EQUITY:
            card.set_script_markers(
                _TRADE_FLAGS_KEY, trade_flag_markers(self._last_result)
            )
        else:
            card.clear_script_markers(_TRADE_FLAGS_KEY)

    def _current_card(self):
        return self.chart_cards[0] if self.chart_cards else None

    def _render_chart(self) -> None:
        card = self._current_card()
        if card is None:
            return

        if self._chart_mode is ChartDisplayMode.EQUITY:
            synthetic = equity_curve_to_candles(self._last_result.equity_curve)
            card.render_historical_data(synthetic)
            card.set_chart_type("line")
            card.clear_script_markers(_TRADE_FLAGS_KEY)
            self._remove_equity_subplot(card)
            return

        # OHLC and BOTH both put real price candles on the main plot.
        card.render_historical_data(self._last_klines)
        card.set_chart_type("candlestick")
        card.render_historical_volume(self._last_volume)

        if (
            self.chart_controls is not None
            and self.chart_controls.is_trade_flags_checked()
        ):
            card.set_script_markers(
                _TRADE_FLAGS_KEY, trade_flag_markers(self._last_result)
            )
        else:
            card.clear_script_markers(_TRADE_FLAGS_KEY)

        if self._chart_mode is ChartDisplayMode.BOTH:
            self._add_or_update_equity_subplot(card)
        else:
            self._remove_equity_subplot(card)

    def _add_or_update_equity_subplot(self, card) -> None:
        x_data, y_data = equity_curve_to_line_data(self._last_result.equity_curve)
        if not self._equity_subplot_added:
            card.add_subplot_indicator(_EQUITY_SUBPLOT_KEY, _EQUITY_SUBPLOT_COLOR)
            self._equity_subplot_added = True
        card.update_indicator_data(_EQUITY_SUBPLOT_KEY, x_data, y_data)

    def _remove_equity_subplot(self, card) -> None:
        if self._equity_subplot_added:
            card.remove_indicator(_EQUITY_SUBPLOT_KEY)
            self._equity_subplot_added = False
