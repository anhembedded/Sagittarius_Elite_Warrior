from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDockWidget, QVBoxLayout, QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.place import Place
from Sagittarius_Elite_Warrior.src.core.contracts.surface import Surface
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.theme import (
    NEUTRAL_SERIES_COLOR,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.timeframe_pin_preferences import (
    TimeframePinPreferences,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.output_source_view import (
    OutputSourceView,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.workbench_surface import (
    WorkbenchSurface,
)
from sagittarius_engine.extensions.pyside_mvc.workbench.output_pane import OutputChannel

from .backtest_modals import BackTestModalsHost
from .backtest_panels import build_panels, place_panels
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
from .monte_carlo_panel import MonteCarloPanel
from .ports.i_backtest_chart_host import IBacktestChartHost
from .run_progress_status import RunProgressStatus
from .run_setup_panel import RunSetupPanel

_EQUITY_SUBPLOT_KEY = "equity"
_EQUITY_SUBPLOT_COLOR = NEUTRAL_SERIES_COLOR  # an equity curve has no verdict
_TRADE_FLAGS_KEY = "backtest_trades"

#: This mode's surface. Declared here because a module may not import
#: `shell/`; `test_backtest_mode_layout.py` holds it equal to
#: `shell/surfaces.py`'s `backtest` entry.
BACKTEST_SURFACE = Surface(
    "backtest",
    owner="backtesting",
    accepts=frozenset({Place.WORKSPACE, Place.NAVIGATOR, Place.RAIL, Place.CONSOLE}),
)


class BackTestView(OutputSourceView):
    """
    @brief The Backtest mode (`EPIC-033L`), laid out as HLD §11.2.1 lists it:
    the result chart in the centre; Run setup (`RunSetupPanel`) on the left;
    Metrics (`BackTestTopPanel`: banners and figures) on the right; Trades
    (`BackTestTradeLogsPanel`) at the bottom, tabbed with Drawdown, Monthly
    returns and Monte Carlo (`backtest_panels.py`); a run's progress in the
    status bar (`run_progress_status.py`). The run log is the Output
    pane's "Backtest" channel (`EPIC-033F`).

    @details Before `EPIC-033L` the same parts were stacked in a `QSplitter`
    with minimum heights adding up to 1000 px, inside a page scroll area,
    under a page header: the chart scrolled with the page and the pickers'
    row scrolled sideways inside it. Docks size to the window, and the
    person moves, tabs or hides them; the mode's perspective keeps it.
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
        self._progress = RunProgressStatus(self)
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

        # The panels need the ViewModel at construction (`EPIC-006E`'s
        # lazy-build contract): built and docked in `set_view_model()`.
        self.run_setup: RunSetupPanel | None = None
        self.top_widget: BackTestTopPanel | None = None
        self.bottom_widget: BackTestTradeLogsPanel | None = None
        self.monte_carlo: MonteCarloPanel | None = None

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers the ViewModel and builds every child that needs it
        (EPIC-006E: top/bottom widgets and the modals). `context_name` is
        unused, kept for `BasePresenter`'s generic wiring."""
        self._view_model = view_model
        self._output = OutputChannel("backtest", "Backtest", view_model.log_model)
        view_model.broker_sim.marketChanged.connect(self._show_marker_sides)
        self._progress.track_run_of(view_model)
        panels = build_panels(view_model)
        place_panels(self._surface, panels)
        self.run_setup = panels.run_setup
        self.top_widget = panels.metrics
        self.bottom_widget = panels.trades
        self.drawdown = panels.drawdown
        self.monthly_returns = panels.monthly_returns
        self.monte_carlo = panels.monte_carlo
        view_model.openMonteCarloRequested.connect(self._show_monte_carlo)

        self._modals_host = BackTestModalsHost(view_model, self)

    def status_widgets(self) -> Sequence[QWidget]:
        """`IStatusSource`: a run's progress, in the status bar."""
        return self._progress.widgets

    def dock_of(self, widget: QWidget) -> QDockWidget:
        """The panel `widget` is the content of."""
        return self._surface.dock_of(widget)

    def _show_monte_carlo(self) -> None:
        """Tools → Monte Carlo brings its panel to the front, opening it
        again if the person closed it."""
        if self.monte_carlo is None:
            return
        dock = self.dock_of(self.monte_carlo)
        dock.show()
        dock.raise_()

    def _show_marker_sides(self) -> None:
        """EPIC-027D, BOT-167 — marker sides and timeframes follow the market."""
        if self._view_model is None:
            return
        market = MarketType(self._view_model.broker_sim.market)
        for card in self.chart_cards:
            card.set_market(market)
        if self.chart_controls is not None:
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
            self.charts_layout.insertWidget(0, self.chart_controls)
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
        container-registered, per-symbol pinned-timeframe store, the same
        seam as `set_symbol_preferences` above. `render_symbol_cards()` hands
        it to every host it builds: a fresh host is built on every symbol
        change, so the store, not a host, has to outlive that rebuild."""
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
        if self._current_card() is None:
            return
        self._render_chart()
        self.chartPreviewRendered.emit()

    @property
    def chart_mode(self) -> ChartDisplayMode:
        return self._chart_mode

    def set_chart_mode(self, mode: ChartDisplayMode) -> None:
        """`PythonBacktestChartHost` supports OHLC/EQUITY/BOTH directly, so
        switching modes never needs a host rebuild — it did while a native
        host (with a narrower supported-mode set) could still be active.

        BUG-158: renders with or without a result (an empty equity series)."""
        self._chart_mode = mode
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
        """`_last_result.trades` narrowed by `chart_controls`'s marker filters
        (PROP-004); every trade when `chart_controls` is `None`. Only called
        once `set_trade_flags_visible()` has confirmed `_last_result` is set."""
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
            synthetic = equity_curve_to_candles(self._equity_curve())
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

    def _equity_curve(self) -> list:
        """The last run's equity curve; empty before any run has a result."""
        return [] if self._last_result is None else self._last_result.equity_curve

    def _add_or_update_equity_subplot(self, card) -> None:
        x_data, y_data = equity_curve_to_line_data(self._equity_curve())
        if not self._equity_subplot_added:
            card.add_subplot_indicator(_EQUITY_SUBPLOT_KEY, _EQUITY_SUBPLOT_COLOR)
            self._equity_subplot_added = True
        card.update_indicator_data(_EQUITY_SUBPLOT_KEY, x_data, y_data)

    def _remove_equity_subplot(self, card) -> None:
        if self._equity_subplot_added:
            card.remove_indicator(_EQUITY_SUBPLOT_KEY)
            self._equity_subplot_added = False
