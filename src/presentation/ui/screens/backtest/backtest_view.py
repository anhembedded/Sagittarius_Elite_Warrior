from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from sagittarius_engine.extensions.pyside_mvc import (
    BaseView,
    OverlayHost,
    create_quick_widget,
)

from .logic.backtest_chart_host import BacktestChartHostFactory, IBacktestChartHost
from .logic.chart_canvas_view import (
    ChartDisplayMode,
    equity_curve_to_candles,
    equity_curve_to_line_data,
    trade_flag_markers,
)
from .logic.chart_controls import BacktestChartControls

_QML_DIR = Path(__file__).parent
_TOP_PANEL_QML = "BackTestTopPanel.qml"
_TRADE_LOGS_QML = "BackTestTradeLogs.qml"
_MODALS_QML = "BackTestModals.qml"

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
    (see `BacktestChartControls`'s own docstring for why). Since BOT-098F6A,
    this class reaches the chart only through `IBacktestChartHost`
    (`logic/backtest_chart_host.py`) via `BacktestChartHostFactory`, never a
    concrete `ChartCard` — that seam is what lets a future native host
    (BOT-098F6B) replace the renderer without this class changing.
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
        self._chart_backend = "auto"
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
        # BOT-087: this direct child deliberately stays out of the layout so
        # a future QML Popup can use the Backtest view's full bounds rather
        # than the small top QQuickWidget that defines the toolbar.
        self.overlay_host = OverlayHost(self)

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        outer_layout.setSpacing(10)

        self.top_widget = create_quick_widget()
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
        # BOT-090: was [600, 200] — 200px is well below what the Trade Logs
        # pane actually needs (BUG-004: rendered header/tabs/pagination,
        # zero rows visible). `_bind_trade_log_minimum_height()` enforces a
        # real floor via setMinimumHeight() regardless of this hint, but
        # starting close to that floor avoids a visible jump/snap on first
        # show.
        main_splitter.setSizes([500, 350])

    def set_view_model(self, view_model, context_name: str = "viewModel") -> None:
        """Registers the screen's ViewModel as a QML context property on
        quick widgets. Must be called before load_qml() — see the
        ordering contract in this class's docstring."""
        self._view_model = view_model
        self._set_context_property(self.top_widget, context_name, view_model)
        self._set_context_property(self.bottom_widget, context_name, view_model)
        self._set_context_property(
            self.overlay_host.quick_widget, context_name, view_model
        )

    def load_qml(self) -> None:
        """Loads this screen's fixed pair of QML documents and modals overlay."""
        self.top_widget.setSource(QUrl.fromLocalFile(str(_QML_DIR / _TOP_PANEL_QML)))
        self.bottom_widget.setSource(
            QUrl.fromLocalFile(str(_QML_DIR / _TRADE_LOGS_QML))
        )
        self.overlay_host.load_content(QUrl.fromLocalFile(str(_QML_DIR / _MODALS_QML)))
        self._bind_top_panel_height()
        self._bind_trade_log_minimum_height()

    def _set_context_property(self, widget, name: str, value: QObject) -> None:
        widget.rootContext().setContextProperty(name, value)

    def _bind_top_panel_height(self) -> None:
        """
        @brief BOT-089 — `top_widget` is `SizeRootObjectToView` (the shared
        default from `create_quick_widget()`, same as every other QML host
        in the app), so the QML root's `implicitHeight` never drives the
        widget's size on its own. This is the one place that reads it back
        and applies it, replacing the `_TOP_PANEL_HEIGHT` constant that had
        already needed bumping once before (120 -> 190, BOT-055) for the
        exact same reason: a hardcoded number ignoring what the content
        actually needs.
        @details Deliberately local to this View, not a change to
        `create_quick_widget()`'s shared resize mode — Settings/Database/
        Dashboard's QML hosts fill whatever space their container gives
        them and must keep doing so; only this screen's top panel is meant
        to size itself to its content.
        """
        root = self.top_widget.rootObject()
        if root is None:
            return
        content_column = root.findChild(QObject, "contentColumn")
        if content_column is None:
            return

        resize_pending = False

        def apply_height() -> None:
            nonlocal resize_pending
            resize_pending = False
            content_column.ensurePolished()
            self.top_widget.setFixedHeight(int(root.property("implicitHeight")))

        def sync_height() -> None:
            nonlocal resize_pending
            if resize_pending:
                return
            resize_pending = True
            QTimer.singleShot(0, apply_height)

        root.implicitHeightChanged.connect(sync_height)
        sync_height()

    def _bind_trade_log_minimum_height(self) -> None:
        """
        @brief BOT-090 — `bottom_widget` sits inside `main_splitter`, whose
        `setSizes([600, 200])` was only ever an initial hint: nothing
        stopped the splitter from squeezing it far below what the table
        actually needs (BUG-004's exact symptom — header/tabs/pagination
        all rendered, zero trade rows visible, because 200px < toolbar +
        table header + 20 rows + pagination by a wide margin).
        @details Unlike `_bind_top_panel_height` (a fixed size, since that
        panel has nothing else competing for space), this applies
        `setMinimumHeight()` — the splitter still distributes extra space
        and the user can still drag it larger, but can never drag it below
        `minimumUsableHeight` (a deliberate "stay usable for N rows" floor
        computed in `BackTestTradeLogs.qml`, not a rediscovered content
        size — a paginated ListView has no single natural height, unlike
        BOT-089's stat cards).
        """
        root = self.bottom_widget.rootObject()
        if root is None:
            return
        toolbar_row = root.findChild(QObject, "toolbarRow")
        if toolbar_row is None:
            return

        def sync_minimum_height() -> None:
            toolbar_row.ensurePolished()
            minimum = int(root.property("minimumUsableHeight"))
            self.bottom_widget.setMinimumHeight(minimum)

        root.minimumUsableHeightChanged.connect(sync_minimum_height)
        sync_minimum_height()

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
                backend=self._effective_chart_backend(),
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

    def set_chart_backend(self, backend: str) -> None:
        """BOT-098F6D: "python" | "native" | "auto", from
        backtest.chart.backend config. Takes effect on the next
        render_symbol_cards() call — an already-built host is not hot-swapped."""
        self._chart_backend = backend

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

    def _effective_chart_backend(self) -> str:
        """BOT-098F6D: native supports OHLC only in this slice — Equity/BOTH
        always render Python regardless of the configured backend, no
        matter which mode a native-backed host happened to be built under."""
        if self._chart_mode is not ChartDisplayMode.OHLC:
            return "python"
        return self._chart_backend

    @property
    def chart_mode(self) -> ChartDisplayMode:
        return self._chart_mode

    def set_chart_mode(self, mode: ChartDisplayMode) -> bool:
        """Returns True when the effective backend changed and the chart
        host was rebuilt from scratch — BackTestPresenter uses this to know
        it must drop any indicator-line bookkeeping tied to the old host
        (BOT-098F6D bug, 2026-08-18: a rebuilt host starts with zero
        indicators, but the presenter kept believing stale ones were still
        registered, which crashed the next visibility toggle and left
        strategy/script lines silently missing)."""
        backend_before = self._effective_chart_backend()
        self._chart_mode = mode
        rebuilt = False
        if self._effective_chart_backend() != backend_before and self._last_symbols:
            # The active host's renderer is no longer valid for this mode
            # (e.g. native + OHLC -> Equity, or back) — rebuild rather than
            # push incompatible data into it. BOT-098F6D acceptance
            # criterion 2 explicitly allows this: "requires view
            # reconstruction on backend change."
            self.render_symbol_cards(self._last_symbols)
            rebuilt = True
        if self._last_result is not None:
            self._render_chart()
        return rebuilt

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

    def refresh_chart(self) -> None:
        """Re-renders whatever data is already cached (last run result or
        preview klines) onto the current host — the public re-entry point
        BackTestPresenter uses after rebuilding the host mid-session
        (BOT-098F6D unsupported-native-feature fallback), instead of
        reaching into this View's private render state directly."""
        if self._last_result is not None or self._last_klines:
            self._render_chart()

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
