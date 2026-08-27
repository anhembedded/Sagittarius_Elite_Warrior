from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QScrollArea, QSplitter, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from sagittarius_engine.extensions.pyside_mvc import BaseView

from .backtest_modals import BackTestModalsHost
from .backtest_top_panel import BackTestTopPanel
from .backtest_trade_logs_panel import BackTestTradeLogsPanel
from .logic.backtest_chart_host import BacktestChartHostFactory
from .logic.chart_canvas_view import (
    ChartDisplayMode,
    equity_curve_to_candles,
    equity_curve_to_line_data,
    trade_flag_markers,
)
from .logic.chart_controls import BacktestChartControls
from .ports.i_backtest_chart_host import IBacktestChartHost

_EQUITY_SUBPLOT_KEY = "equity"
_EQUITY_SUBPLOT_COLOR = (
    Palette.ACCENT  # Theme.accent's hex — chart_card has no Qt theme singleton access
)
_TRADE_FLAGS_KEY = "backtest_trades"
_CHART_MINIMUM_HEIGHT = 550
_TRADE_LOGS_MINIMUM_HEIGHT = 450
_MAIN_SPLITTER_MINIMUM_HEIGHT = 1000


class BackTestView(BaseView):
    """
    @brief View for the Backtest Screen: plain QtWidgets throughout
    (EPIC-006E) — a top toolbar/metrics panel (`BackTestTopPanel`), a tall
    chart area (`ChartCard`/pyqtgraph), and a bottom trade-logs panel
    (`BackTestTradeLogsPanel`), inside a scrollable `QSplitter` layout.
    @details
    Wraps content inside a `QScrollArea` to allow smooth vertical rolling on
    any viewport height without squeezing the candlestick chart or trade logs.
    """

    chartPreviewRendered = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_model = None
        self._display_timezone = "UTC"
        # Self-constructed default so a bare BackTestView() (every existing
        # unit test) still works; BackTestPresenter overrides this with the
        # DI-resolved instance via set_chart_host_factory() in production
        # (BOT-098F6D) — BackTestView itself has no container access.
        self._chart_host_factory = BacktestChartHostFactory()
        self._last_symbols: list[str] = []
        self.chart_cards: list[IBacktestChartHost] = []
        self._chart_dev_mode = False
        self._chart_opengl_enabled = False
        self._chart_cached_interaction_enabled = False
        self.chart_controls: BacktestChartControls | None = None
        self._chart_mode = ChartDisplayMode.OHLC
        self._equity_subplot_added = False
        self._last_result = None
        self._last_klines: list = []
        self._last_volume: list = []
        self._setup_ui()
        # BackTestModalsHost (EPIC-006E3) owns all 11 modal QDialogs, built
        # lazily in set_view_model() below — replaces OverlayHost/QQuickWidget
        # (BOT-087's full-window click-through overlay existed only because
        # QML Popups needed a host; a real QDialog is already modal and
        # self-centering, no host widget required).
        self._modals_host: BackTestModalsHost | None = None

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        outer_layout.addWidget(self.scroll_area)

        self.scroll_content = QWidget()
        self._scroll_content_layout = QVBoxLayout(self.scroll_content)
        self._scroll_content_layout.setContentsMargins(10, 10, 10, 10)
        self._scroll_content_layout.setSpacing(10)

        # BackTestTopPanel (EPIC-006E) needs the ViewModel at construction
        # time (same lazy-build contract as DevBoardPanel, EPIC-006D) — built
        # in set_view_model() below, not here, and inserted at index 0.
        self.top_widget: BackTestTopPanel | None = None

        self._main_splitter = QSplitter(Qt.Orientation.Vertical)
        self._main_splitter.setMinimumHeight(_MAIN_SPLITTER_MINIMUM_HEIGHT)
        self._scroll_content_layout.addWidget(self._main_splitter, 1)

        self.charts_container = QWidget()
        self.charts_container.setMinimumHeight(_CHART_MINIMUM_HEIGHT)
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(0)
        self._main_splitter.addWidget(self.charts_container)

        # BackTestTradeLogsPanel (EPIC-006E) also needs the ViewModel at
        # construction — built in set_view_model() below, added as the
        # splitter's 2nd child there.
        self.bottom_widget: BackTestTradeLogsPanel | None = None

        self.scroll_area.setWidget(self.scroll_content)

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers the screen's ViewModel and builds every child that
        needs it at construction time (EPIC-006E: `top_widget`,
        `bottom_widget`, and the 11 modal `QDialog`s owned by
        `_modals_host` — all plain QtWidgets now, no QML context property
        registration left to do). `context_name` is unused, kept only for
        call-site compatibility with `BasePresenter`'s generic wiring."""
        self._view_model = view_model
        self.top_widget = BackTestTopPanel(view_model)
        self._scroll_content_layout.insertWidget(0, self.top_widget)

        self.bottom_widget = BackTestTradeLogsPanel(view_model)
        self.bottom_widget.setMinimumHeight(
            max(_TRADE_LOGS_MINIMUM_HEIGHT, self.bottom_widget.minimum_usable_height())
        )
        self._main_splitter.addWidget(self.bottom_widget)
        self._main_splitter.setStretchFactor(0, 3)
        self._main_splitter.setStretchFactor(1, 2)
        self._main_splitter.setSizes(
            [_CHART_MINIMUM_HEIGHT, _TRADE_LOGS_MINIMUM_HEIGHT]
        )

        self._modals_host = BackTestModalsHost(view_model, self)

    def apply_ui_mode(self, mode, section_key: str = "main") -> None:
        """Receives FSM state changes from BasePresenter and forwards them to
        the ViewModel's `uiMode` property — same duck-typed hook
        `QmlHostView.apply_ui_mode` provides for single-document screens."""
        if self._view_model is None:
            return
        mode_value = getattr(mode, "value", mode)
        self._view_model.set_ui_mode(str(mode_value))

    def render_symbol_cards(self, symbols: list[str]) -> list[IBacktestChartHost]:
        for i in reversed(range(self.charts_layout.count())):
            item = self.charts_layout.itemAt(i)
            widget = item.widget()
            if widget:
                if hasattr(widget, "cleanup"):
                    widget.cleanup()
                self.charts_layout.removeItem(item)
                widget.deleteLater()

        self._last_symbols = list(symbols)
        self.chart_cards = []
        self.chart_controls = None
        for symbol in symbols:
            host = self._chart_host_factory.create(
                symbol,
                use_opengl=self._chart_opengl_enabled,
                cached_interaction=self._chart_cached_interaction_enabled,
            )
            host.set_dev_mode(self._chart_dev_mode)
            host.set_display_timezone(self._display_timezone)
            self.chart_cards.append(host)
            self.charts_layout.addWidget(host.widget, 1)

        if self.chart_cards:
            self.chart_controls = BacktestChartControls()
            self.chart_cards[0].add_to_header(self.chart_controls)

        return self.chart_cards

    def set_chart_dev_mode(self, enabled: bool) -> None:
        """Applies the developer instrumentation state to current and future charts."""
        self._chart_dev_mode = bool(enabled)
        for card in self.chart_cards:
            card.set_dev_mode(self._chart_dev_mode)

    def set_chart_opengl_enabled(self, enabled: bool) -> None:
        """Selects the render backend for chart cards created from now on."""
        self._chart_opengl_enabled = bool(enabled)

    def set_chart_cached_interaction_enabled(self, enabled: bool) -> None:
        """Selects cached-frame pan/zoom for chart cards created from now on."""
        self._chart_cached_interaction_enabled = bool(enabled)

    def set_chart_host_factory(self, factory: BacktestChartHostFactory) -> None:
        """BOT-098F6D: BackTestPresenter injects the DI-resolved factory here
        (BackTestView itself has no container access) before the first
        render_symbol_cards() call."""
        self._chart_host_factory = factory

    def set_display_timezone(self, tz_name: str) -> None:
        """Propagates display timezone to all active chart cards."""
        self._display_timezone = tz_name
        for card in self.chart_cards:
            if hasattr(card, "set_display_timezone"):
                card.set_display_timezone(tz_name)

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

    def on_preview_data_ready(self, klines: list, volume: list) -> None:
        """Render local candles for a newly selected range before a run exists."""
        self._last_result = None
        self._last_klines = klines
        self._last_volume = volume
        card = self._current_card()
        if card is None:
            return
        card.render_historical_data(klines)
        card.set_chart_type("candlestick")
        card.render_historical_volume(volume)
        card.clear_script_markers(_TRADE_FLAGS_KEY)
        self.chartPreviewRendered.emit()
        self._remove_equity_subplot(card)

    @property
    def chart_mode(self) -> ChartDisplayMode:
        return self._chart_mode

    def set_chart_mode(self, mode: ChartDisplayMode) -> None:
        """`PythonBacktestChartHost` supports OHLC/EQUITY/BOTH directly, so
        switching modes never needs a host rebuild — it did while a native
        host (with a narrower supported-mode set) could still be active."""
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
            self._last_result is not None
            and self.chart_controls is not None
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
