from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.assets import Palette
from Sagittarius_Elite_Warrior.src.support.ui_kit.output_source_view import (
    OutputSourceView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import OutputChannel

from .backtest_modals import BackTestModalsHost
from .backtest_top_panel import BackTestTopPanel
from .backtest_trade_logs_panel import BackTestTradeLogsPanel
from .logic.backtest_chart_host import BacktestChartHostFactory
from .logic.chart_canvas_view import (
    ChartDisplayMode,
    equity_curve_to_candles,
    equity_curve_to_line_data,
    filter_trades_for_markers,
    trade_flag_markers_for_trades,
    trade_marker_badges_for_trades,
)
from .logic.chart_controls import BacktestChartControls
from .ports.i_backtest_chart_host import IBacktestChartHost
from .run_setup_panel import RunSetupPanel

_EQUITY_SUBPLOT_KEY = "equity"
_EQUITY_SUBPLOT_COLOR = (
    Palette.ACCENT  # Theme.accent's hex — chart_card has no Qt theme singleton access
)
_TRADE_FLAGS_KEY = "backtest_trades"

#: This mode's surface. Declared here because a module may not import
#: `shell/`; `test_backtest_mode_layout.py` holds it equal to
#: `shell/surfaces.py`'s `backtest` entry.
BACKTEST_SURFACE = Surface(
    "backtest",
    owner="backtesting",
    accepts=frozenset({Place.WORKSPACE, Place.NAVIGATOR, Place.RAIL, Place.CONSOLE}),
)
#: The panels HLD §11.2.1 lists for this mode, by their dock titles.
RUN_SETUP_DOCK = "Run setup"
METRICS_DOCK = "Metrics"
TRADES_DOCK = "Trades"


class BackTestView(OutputSourceView):
    """
    @brief The Backtest mode (`EPIC-033L`), laid out as HLD §11.2.1 lists it:
    the result chart in the centre; Run setup (`RunSetupPanel`) on the left;
    Metrics (`BackTestTopPanel`: banners and figures) on the right; Trades
    (`BackTestTradeLogsPanel`) at the bottom. The run log is the Output
    pane's "Backtest" channel (`EPIC-033F`).

    @details Before `EPIC-033L` the same parts were stacked in a `QSplitter`
    with minimum heights adding up to 1000 px, inside a page scroll area,
    under a `PageShell` header: the chart scrolled with the page and the
    pickers' row scrolled sideways inside it. Docks size to the window, and
    the person moves, tabs or hides them; the mode's perspective keeps it.
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
        # Follow-up to `EPIC-015` Phase 4: self-constructed default so a bare
        # BackTestView() (every existing unit test) still works unpersisted;
        # BackTestPresenter overrides this with the DI-resolved, shared store
        # via set_timeframe_pin_preferences() in production — same shape and
        # reason as `_chart_host_factory` just above.
        self._timeframe_pin_preferences = TimeframePinPreferences()
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
        self._surface = WorkbenchSurface(BACKTEST_SURFACE)
        outer_layout.addWidget(self._surface)

        self.charts_container = QWidget()
        self.charts_layout = QVBoxLayout(self.charts_container)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self._surface.place_widget(Place.WORKSPACE, self.charts_container)

        # The three panels need the ViewModel at construction (`EPIC-006E`'s
        # lazy-build contract): built and docked in `set_view_model()`.
        self.run_setup: RunSetupPanel | None = None
        self.top_widget: BackTestTopPanel | None = None
        self.bottom_widget: BackTestTradeLogsPanel | None = None

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers the ViewModel and builds every child that needs it
        (EPIC-006E: top/bottom widgets and the modals). `context_name` is
        unused, kept for `BasePresenter`'s generic wiring."""
        self._view_model = view_model
        self._output = OutputChannel("backtest", "Backtest", view_model.log_model)
        view_model.broker_sim.marketChanged.connect(self._show_marker_sides)
        self.run_setup = RunSetupPanel(view_model)
        self.top_widget = BackTestTopPanel(view_model)
        self.bottom_widget = BackTestTradeLogsPanel(view_model)
        # `BUG-004`: squeezed below this floor the hand-built row list shows
        # its header and no row. Kept while the list is hand-built; the
        # trades table built from its column specs (the next stage of
        # `EPIC-033L`) scrolls at any height and needs none.
        self.bottom_widget.setMinimumHeight(self.bottom_widget.minimum_usable_height())
        self._surface.place_widget(
            Place.NAVIGATOR, self.run_setup, title=RUN_SETUP_DOCK
        )
        self._surface.place_widget(Place.RAIL, self.top_widget, title=METRICS_DOCK)
        self._surface.place_widget(Place.CONSOLE, self.bottom_widget, title=TRADES_DOCK)

        self._modals_host = BackTestModalsHost(view_model, self)

    def _show_marker_sides(self) -> None:
        """EPIC-027D — the chart's side filter follows the screen's market."""
        if self.chart_controls is not None and self._view_model is not None:
            market = MarketType(self._view_model.broker_sim.market)
            self.chart_controls.show_sides_for(market)

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
                timeframe_pin_preferences=self._timeframe_pin_preferences,
            )
            host.set_dev_mode(self._chart_dev_mode)
            host.set_display_timezone(self._display_timezone)
            self.chart_cards.append(host)
            self.charts_layout.addWidget(host.widget, 1)

        if self.chart_cards:
            self.chart_controls = BacktestChartControls()
            self.chart_cards[0].add_to_header(self.chart_controls)
            self._show_marker_sides()

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

    def set_symbol_preferences(self, preferences) -> None:
        """EPIC-014: BackTestPresenter injects the container-registered
        favourites/recents store here, the same seam and the same reason as
        `set_chart_host_factory` below — BackTestView has no container
        access. Forwarded to `_modals_host`, which owns the symbol picker;
        a no-op before `set_view_model()` has built one, and the host keeps
        its own unpersisted store in that case."""
        if self._modals_host is not None:
            self._modals_host.set_symbol_preferences(preferences)

    def set_timeframe_pin_preferences(
        self, preferences: TimeframePinPreferences
    ) -> None:
        """Follow-up to `EPIC-015` Phase 4: `BackTestPresenter` injects the
        container-registered, per-symbol pinned-timeframe store here, the
        same seam and reason as `set_symbol_preferences` above. Stored for
        `render_symbol_cards()` to hand to every chart host it builds from
        now on — Backtest has exactly one chart at a time, but a fresh host
        is built on every symbol change, so the store (not a single host)
        is what has to outlive that rebuild."""
        self._timeframe_pin_preferences = preferences

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
                _TRADE_FLAGS_KEY,
                self._filtered_trade_flag_markers(),
                self._filtered_trade_flag_badges(),
            )
        else:
            card.clear_script_markers(_TRADE_FLAGS_KEY)

    def refresh_trade_flag_filters(self) -> None:
        """PROP-004 — a marker filter control changed; re-apply
        `set_trade_flags_visible()` with the checkbox's own current state so
        this never overrides the user's separate show/hide toggle."""
        if self.chart_controls is not None:
            self.set_trade_flags_visible(self.chart_controls.is_trade_flags_checked())

    def _filtered_trades(self):
        """`_last_result.trades` narrowed by `chart_controls`'s marker
        filters (PROP-004) — a `chart_controls is None` host (never
        happens once a run has results, but the type is `| None`) falls
        back to every trade. Only called once `set_trade_flags_visible()`'s
        own guard has already confirmed `_last_result is not None`."""
        trades = self._last_result.trades
        if self.chart_controls is not None:
            trades = filter_trades_for_markers(
                trades,
                outcome=self.chart_controls.outcome_filter(),
                side=self.chart_controls.side_filter(),
                min_abs_pnl_percent=self.chart_controls.min_pnl_threshold(),
            )
        return trades

    def _filtered_trade_flag_markers(self):
        return trade_flag_markers_for_trades(self._filtered_trades())

    def _filtered_trade_flag_badges(self):
        """`PROP-003` — badges for the same filtered trades, in the same
        order `_filtered_trade_flag_markers()` builds its markers in, so
        the two stay positionally aligned for `MarkerLayer.set_markers()`."""
        return trade_marker_badges_for_trades(self._filtered_trades())

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
                _TRADE_FLAGS_KEY,
                self._filtered_trade_flag_markers(),
                self._filtered_trade_flag_badges(),
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
