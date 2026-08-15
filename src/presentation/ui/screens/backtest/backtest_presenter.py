from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QFileDialog
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_toolbar import (
    DEFAULT_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.indicator_script_runner import (
    IndicatorScriptRunner,
    qualified_line_name,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.kline_mapping import (
    map_klines,
    map_volume,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .backtest_view_model import BackTestViewModel
from .logic.backtest_limitations_view import build_backtest_limitations
from .logic.backtest_run_config import BacktestRunConfig
from .logic.backtest_state import BacktestUiState
from .logic.bot_params_form import build_bot_params_schema, parse_bot_params
from .logic.chart_canvas_view import ChartDisplayMode
from .logic.performance_metrics_view import (
    build_extended_stat_cards,
    build_primary_stat_cards,
    build_result_warning_text,
    stat_cards_to_qml,
)
from .logic.result_formatter import format_result_summary
from .logic.strategy_indicator_lines import (
    assign_strategy_line_colors,
    compute_strategy_indicator_lines,
)
from .logic.time_range_preset import TimeRangePreset, resolve_time_range
from .logic.trade_log_export import export_trades_to_csv
from .logic.trade_log_filter import (
    TradeLogFilter,
    filter_trade_log_rows,
    search_trade_log_rows,
)
from .logic.trade_log_pagination import paginate_trade_log_rows, total_pages
from .logic.trade_log_row import (
    TradeLogRow,
    build_trade_log_rows,
    trade_log_rows_to_qml,
)

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .backtest_view import BackTestView

logger = logging.getLogger("App.BackTestPresenter")

_TRACE_PREFIX = "BACKTEST_TRACE"

#: Only used when IConfig's own DEFAULT_SYMBOLS is empty (e.g. a fresh
#: install, Settings never opened) — BOT-058: the real default symbol comes
#: from config (self._symbol, set in __init__), not this constant. Backtest
#: still has no symbol picker (out of scope, not requested), so whichever
#: symbol this resolves to is the only one this screen ever backtests.
_FALLBACK_SYMBOL = "ETHUSDT"

_CUSTOM_TIME_FORMAT = "%Y-%m-%d %H:%M"

_INVALID_CAPITAL_MESSAGE = "Vốn ban đầu không hợp lệ: {value!r}"
_NON_POSITIVE_CAPITAL_MESSAGE = "Vốn ban đầu phải lớn hơn 0."
_INVALID_CUSTOM_START_MESSAGE = (
    f"Ngày bắt đầu không hợp lệ — định dạng {_CUSTOM_TIME_FORMAT}."
)
_INVALID_CUSTOM_RANGE_MESSAGE = "Ngày bắt đầu phải trước ngày kết thúc."
_NO_STRATEGY_MESSAGE = "Chưa có chiến lược nào được đăng ký."
_RUNNING_MESSAGE = "Đang chạy backtest..."
_SYNCING_MESSAGE = "Đang đồng bộ dữ liệu..."
_ZERO_TRADES_MESSAGE = (
    "Backtest chạy xong nhưng không có giao dịch nào trong khoảng thời gian đã chọn."
)

_EXPORT_DIALOG_TITLE = "Xuất Trade Logs"
_EXPORT_DEFAULT_FILENAME = "trade_logs.csv"
_EXPORT_FILE_FILTER = "CSV Files (*.csv)"

#: GetHistoricalKlinesQuery.limit has no "unlimited" sentinel (unlike
#: RunStaticBacktestCommand.limit, which IMarketDataRepository.get_klines
#: treats as None = no cap) — this is a generously large stand-in so the
#: chart's candle set matches what the backtest itself evaluated. 5000 hourly
#: bars is ~208 days; 5000 daily bars is ~13 years.
_CHART_KLINES_FETCH_LIMIT = 5000


def _humanize_strategy_key(key: str) -> str:
    return key.replace("_", " ").title()


def _parse_custom_datetime(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), _CUSTOM_TIME_FORMAT).replace(tzinfo=UTC)
    except (ValueError, AttributeError):
        return None


class BackTestPresenter(BasePresenter):
    """
    @brief Presenter for the Backtest Screen (BOT-022 — Epic BOT-006 Phase 1
    / Epic BOT-040).

    @details
    Threading contract, same as `DataManagementPresenter`: `_run_backtest`
    executes on `IThreadManager`'s pool and must only emit signals — the 3
    `_backtest*Signal`s below are the sole bridge back to the main thread,
    where the matching `_on_backtest_*` slots update the ViewModel and the
    FSM. `RunStaticBacktestCommandHandler.execute()` is otherwise
    synchronous and pure (returns `BacktestResult | None` directly), so
    unlike the Dashboard/Database screens there is no progress-event stream
    to subscribe to — one dispatch, one result.
    """

    INITIAL_STATE = BacktestUiState.IDLE

    _backtestSucceededSignal = Signal(object)  # BacktestResult
    _backtestEmptySignal = Signal(str, object)  # message, BacktestRunConfig (no data)
    _backtestFailedSignal = Signal(str)  # error message
    _chartDataReadySignal = Signal(object, list, list)  # result, klines, volume
    # BOT-060: line_name, color, x_data, y_data — one emit per line, after
    # the whole run has been fed (same O(N) reasoning as BOT-036's feed_all).
    _chartStrategyLineSignal = Signal(str, str, list, list)
    # BOT-064: user-picked reference indicator scripts (RSI/MACD/...),
    # independent of the strategy's own lines above — same 4-signal shape
    # DashboardPresenter uses for IndicatorScriptRunner's 4 output channels.
    _chartScriptLineSignal = Signal(str, list, list)  # qualified name, x, y
    _chartScriptRegionSignal = Signal(str, list)  # script key, spans
    _chartScriptInfoSignal = Signal(str, list)  # script key, info fields
    _chartScriptMarkerSignal = Signal(str, list)  # script key, markers
    _syncSucceededSignal = Signal()
    _syncFailedSignal = Signal(str)  # error message

    def __init__(self, view: BackTestView, container: IContainer) -> None:
        super().__init__(view, container)

        # BOT-058: read from the same shared IConfig Settings edits
        # (DEFAULT_SYMBOLS/DEFAULT_INTERVAL), instead of a hardcoded
        # constant that happened to coincidentally match what Dev Board
        # syncs by default — read once at construction, same as
        # SettingsPresenter._load_from_config does for its own fields.
        config_values = self.config.get_all()
        default_symbols = config_values.get("DEFAULT_SYMBOLS") or []
        self._symbol: str = default_symbols[0] if default_symbols else _FALLBACK_SYMBOL
        default_interval = config_values.get("DEFAULT_INTERVAL") or ""

        # BOT-059: set only by _on_backtest_empty (a real "no historical
        # data" result), cleared by any successful run or successful sync —
        # the single source of truth for whether "Đồng bộ ngay" is offered.
        self._last_no_data_config: BacktestRunConfig | None = None

        # BOT-057: the single source of truth the Trade Logs table's
        # filter/search/pagination all read from — the ViewModel only ever
        # holds the CURRENT PAGE's already-formatted rows, never the full
        # list, so it can't itself re-derive a different page/filter.
        self._all_trades: list[Trade] = []

        # BOT-047: values for the CURRENTLY SELECTED strategy's declared
        # input_*() parameters, from the last successful "Lưu & Re-Backtest".
        # None (the default) runs every declared default — same as never
        # having opened the modal. Reset to None whenever the selected
        # strategy changes (a different strategy has a different schema
        # entirely, so stale values would either be silently ignored or
        # raise "param nobody declares").
        self._strategy_params: dict[str, Any] | None = None

        self._strategy_registry: StrategyRegistry = container.resolve(StrategyRegistry)
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        # BOT-060: names of the currently-drawn strategy indicator lines
        # (added to as `_on_chart_strategy_line` registers each one on the
        # chart) — read by `_on_ema_toggled`/`_start_backtest_run` so both
        # can act on "whatever is on the chart right now" without needing to
        # know which strategy or how many lines produced it.
        self._active_strategy_lines: set[str] = set()

        self._script_registry: IndicatorScriptRegistry = container.resolve(
            IndicatorScriptRegistry
        )
        # BOT-064: user-picked reference scripts, independent of the
        # strategy's own lines above — batch-only (rebuild()+feed_all() once
        # per run), same reasoning BOT-056 originally had for this class
        # before BOT-060 moved the *strategy* lines to a separate mechanism.
        # Enabled keys are snapshotted at "Chạy Backtest" click time
        # (_start_backtest_run → self._chart_script_keys), never read live
        # mid-run — same "no retroactive effect" rule the Dev Board
        # checklist follows (TC-GAP-07).
        self._chart_script_runner = IndicatorScriptRunner(
            registry=self._script_registry,
            emit_line=self._chartScriptLineSignal.emit,
            emit_region=self._chartScriptRegionSignal.emit,
            emit_info=self._chartScriptInfoSignal.emit,
            emit_markers=self._chartScriptMarkerSignal.emit,
            on_error=logger.warning,
        )
        self._chart_script_keys: list[str] = []

        self._view_model = BackTestViewModel()
        view.set_view_model(self._view_model)
        self._view_model.script_model.set_available(self._script_registry.available())
        # An invalid/empty DEFAULT_INTERVAL (unset config, or a hand-edited
        # user_config.json with a typo) is left alone — BackTestViewModel
        # already defaults to DEFAULT_TIMEFRAMES[0] ("1m") internally, the
        # fastest timeframe and so the one most likely to have synced data.
        if default_interval in DEFAULT_TIMEFRAMES:
            self._view_model.selectedTimeframe = default_interval
        self._view_model.set_strategy_options(
            [
                # category/description are blank until a registered strategy
                # actually carries them (BOT-046/BOT-047) — StrategyComboBox
                # (built for the fuller BOT-040 mockup) expects both roles.
                {
                    "key": key,
                    "name": _humanize_strategy_key(key),
                    "category": "",
                    "description": "",
                }
                for key in sorted(self._strategy_registry.available())
            ]
        )
        self._refresh_bot_params_schema()

        if self.fsm:
            self.fsm.add_transition(BacktestUiState.IDLE, BacktestUiState.RUNNING)
            self.fsm.add_transition(BacktestUiState.RUNNING, BacktestUiState.IDLE)
            self.fsm.add_transition(BacktestUiState.RUNNING, BacktestUiState.ERROR)
            self.fsm.add_transition(BacktestUiState.ERROR, BacktestUiState.IDLE)
            # BOT-059: "Đồng bộ ngay" affordance — SYNCING is a distinct
            # state, not a bool bolted onto RUNNING, so a sync-in-flight and
            # a backtest-in-flight can never be represented at the same time.
            self.fsm.add_transition(BacktestUiState.IDLE, BacktestUiState.SYNCING)
            self.fsm.add_transition(BacktestUiState.SYNCING, BacktestUiState.RUNNING)
            self.fsm.add_transition(BacktestUiState.SYNCING, BacktestUiState.IDLE)

        # Must be called explicitly at the end of __init__ per BasePresenter
        # contract, and before load_qml() so QML parses against a ready model.
        self._connect_ui_signals()
        self._connect_engine_events()

        # After render_symbol_cards(): view.chart_controls doesn't exist
        # until the ChartCard it's attached to has been built.
        view.render_symbol_cards([self._symbol])
        self._connect_chart_controls()
        view.load_qml()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        self._view_model.runBacktestRequested.connect(self._on_run_backtest)
        self._view_model.syncRequested.connect(self._on_request_sync)
        self._view_model.selectedStrategyKeyChanged.connect(
            self._on_strategy_selection_changed
        )
        self._view_model.botParamsSaveRequested.connect(
            self._on_bot_params_save_requested
        )
        self._backtestSucceededSignal.connect(self._on_backtest_succeeded)
        self._backtestEmptySignal.connect(self._on_backtest_empty)
        self._backtestFailedSignal.connect(self._on_backtest_failed)
        self._chartDataReadySignal.connect(self._on_chart_data_ready)
        self._chartStrategyLineSignal.connect(self._on_chart_strategy_line)
        self._chartScriptLineSignal.connect(self._on_chart_script_line)
        self._chartScriptRegionSignal.connect(self._on_chart_script_region)
        self._chartScriptInfoSignal.connect(self._on_chart_script_info)
        self._chartScriptMarkerSignal.connect(self._on_chart_script_marker)
        self._syncSucceededSignal.connect(self._on_sync_succeeded)
        self._syncFailedSignal.connect(self._on_sync_failed)
        self._view_model.tradeLogQueryChanged.connect(self._on_trade_log_query_changed)
        self._view_model.tradeLogExportRequested.connect(
            self._on_trade_log_export_requested
        )

    def _connect_engine_events(self) -> None:
        """Nothing to subscribe to: `RunStaticBacktestCommandHandler` returns
        its `BacktestResult` synchronously to the dispatch call below. It
        also emits `BacktestCompletedEvent`/`BacktestFailedEvent` on the
        event bus (for other future subscribers), but this screen already
        has its result from the return value and has no need to also listen
        for its own echo."""

    def _connect_chart_controls(self) -> None:
        """`BacktestChartControls` (native, owned by `BackTestView`) only
        emits signals — same split as the QML ViewModel — so the actual
        chart-mutation logic (which needs `self._active_strategy_lines`'s
        state) lives here, not in the View."""
        controls = self.view.chart_controls
        if controls is None:
            return
        controls.sig_mode_changed.connect(self._on_chart_mode_changed)
        controls.sig_ema_toggled.connect(self._on_ema_toggled)
        controls.sig_volume_toggled.connect(self.view.set_volume_visible)
        controls.sig_trade_flags_toggled.connect(self.view.set_trade_flags_visible)

    def _log_dev_trace(self, action: str, **fields: object) -> None:
        if not self.config.get(DEV_MODE_CONFIG_KEY, False):
            return
        suffix = " ".join(f"{key}={value!r}" for key, value in fields.items())
        logger.info(f"{_TRACE_PREFIX} action={action} {suffix}".rstrip())

    # ================================================================== #
    # Qt Slots — main thread
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _on_run_backtest(self) -> None:
        if self.fsm.current_state != BacktestUiState.IDLE:
            self._log_dev_trace(
                "run_ignored",
                state=self.fsm.current_state,
            )
            return
        self._log_dev_trace(
            "run_requested",
            strategy=self._view_model.selectedStrategyKey,
            timeframe=self._view_model.selectedTimeframe,
            capital=self._view_model.initialCapitalText,
            preset=self._view_model.timeRangePreset,
        )
        config = self._build_run_config()
        if config is None:
            return
        self.fsm.transition_to(BacktestUiState.RUNNING)
        self._log_dev_trace("run_transitioned", state=self.fsm.current_state)
        self._start_backtest_run(config)

    def _start_backtest_run(self, config: BacktestRunConfig) -> None:
        """Shared by the "Chạy Backtest" click and the post-sync auto-resubmit
        (`_on_sync_succeeded`) — callers are responsible for their own FSM
        transition into RUNNING first (IDLE->RUNNING vs SYNCING->RUNNING are
        different edges), this only does the actual submit."""
        removed_strategy_lines = len(self._active_strategy_lines)
        self._log_dev_trace(
            "run_submit_start",
            strategy=config.strategy_key,
            timeframe=config.timeframe.value,
            start=config.start_time,
            end=config.end_time,
            has_params=bool(config.strategy_params),
            removed_strategy_lines=removed_strategy_lines,
        )
        # Must happen here, on the main thread, BEFORE the background run
        # even starts — this reads self._active_strategy_lines, which
        # _fetch_and_emit_chart_data (background thread) will repopulate as
        # it draws the new run's lines; clearing after that started would
        # race and could remove lines the new run just added.
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is not None:
            for name in self._active_strategy_lines:
                card.remove_indicator(name)
            self._chart_script_runner.clear_from_chart(card)
        self._active_strategy_lines.clear()

        # BOT-064: snapshot which reference scripts are enabled right now —
        # read fresh in the background thread would honor a checkbox toggle
        # mid-run, breaking the same "no retroactive effect" rule the Dev
        # Board checklist follows.
        self._chart_script_keys = self._view_model.script_model.enabled_keys
        self._log_dev_trace(
            "run_snapshot_scripts",
            script_keys=self._chart_script_keys,
        )

        self._view_model.set_result(_RUNNING_MESSAGE, is_error=False)
        self._log_dev_trace("run_worker_submitted")
        self._thread_manager.submit(self._run_backtest, config)

    @Slot(object)
    @safe_ui_action
    def _on_backtest_succeeded(self, result: BacktestResult) -> None:
        """Fires for every real `BacktestResult`, trades or not — stat cards
        (BOT-055) always populate from it (0 trades means every card reads
        0/neutral, never "no cards"); only the status message differs."""
        self._log_dev_trace(
            "run_succeeded",
            trades=len(result.trades),
            net_profit_percent=result.metrics.net_profit_percent,
        )
        self._last_no_data_config = None
        self._view_model.set_needs_data_sync(False)
        self._view_model.set_stat_cards(
            stat_cards_to_qml(build_primary_stat_cards(result)),
            stat_cards_to_qml(build_extended_stat_cards(result)),
        )
        self._view_model.set_result_warning_text(build_result_warning_text(result))
        self._view_model.set_limitations(build_backtest_limitations(result))
        message = (
            format_result_summary(result)
            if result.trades
            else f"{_ZERO_TRADES_MESSAGE}\n\n{format_result_summary(result)}"
        )
        self._view_model.set_result(message, is_error=False)
        self._all_trades = result.trades
        self._refresh_trade_log()
        self.fsm.transition_to(BacktestUiState.IDLE)

    @Slot(str, object)
    @safe_ui_action
    def _on_backtest_empty(self, message: str, config: BacktestRunConfig) -> None:
        """Only for "no historical data at all" — there is no `BacktestResult`
        to build stat cards from, so the panel is cleared. Caches `config` so
        "Đồng bộ ngay" (`_on_request_sync`) knows exactly what to sync and,
        on success, what to re-run."""
        self._last_no_data_config = config
        self._view_model.set_needs_data_sync(True)
        self._view_model.set_stat_cards([], [])
        self._view_model.set_result_warning_text("")
        self._view_model.set_limitations([])
        self._view_model.set_result(message, is_error=False)
        self._all_trades = []
        self._refresh_trade_log()
        if self.fsm.current_state != BacktestUiState.IDLE:
            self.fsm.transition_to(BacktestUiState.IDLE)
        self._log_dev_trace("run_empty", message=message)

    @Slot(str)
    @safe_ui_action
    def _on_backtest_failed(self, message: str) -> None:
        self._log_dev_trace("run_failed", message=message)
        self._view_model.set_stat_cards([], [])
        self._view_model.set_result_warning_text("")
        self._view_model.set_limitations([])
        self._view_model.set_result(f"Lỗi: {message}", is_error=True)
        self._all_trades = []
        self._refresh_trade_log()
        self.fsm.transition_to(BacktestUiState.IDLE)

    @Slot(object, list, list)
    @safe_ui_action
    def _on_chart_data_ready(
        self, result: BacktestResult, klines: list, volume: list
    ) -> None:
        self._log_dev_trace(
            "chart_data_ready",
            klines=len(klines),
            volume=len(volume),
            trades=len(result.trades),
        )
        self.view.on_backtest_data_ready(result, klines, volume)

    @Slot(str, str, list, list)
    @safe_ui_action
    def _on_chart_strategy_line(
        self, name: str, color: str, x_data: list, y_data: list
    ) -> None:
        """BOT-060: one call per strategy indicator line, emitted once the
        whole run has been fed (`_fetch_and_emit_chart_data`) — adds the
        curve on first use, same as `IndicatorScriptRunner.draw()` does for
        Dev Board scripts, just without needing that class at all (a
        strategy has no `.line_colors()`/`.compute()` to drive it)."""
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is None:
            return
        if name not in self._active_strategy_lines:
            card.add_overlay_indicator(name, color)
            self._active_strategy_lines.add(name)
        card.update_indicator_data(name, x_data, y_data)

    @Slot(str, list, list)
    @safe_ui_action
    def _on_chart_script_line(self, name: str, x_data: list, y_data: list) -> None:
        """BOT-064: one call per user-picked reference script line, mirrors
        DashboardPresenter._on_indicator_data — pure delegate to
        IndicatorScriptRunner.draw(), which registers the overlay/subplot
        curve on first use and knows the script's own line color."""
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is not None:
            self._chart_script_runner.draw(card, name, x_data, y_data)

    @Slot(str, list)
    @safe_ui_action
    def _on_chart_script_region(self, key: str, spans: list) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is not None:
            self._chart_script_runner.draw_region(card, key, spans)

    @Slot(str, list)
    @safe_ui_action
    def _on_chart_script_info(self, key: str, fields: list) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is not None:
            self._chart_script_runner.draw_info(card, key, fields)

    @Slot(str, list)
    @safe_ui_action
    def _on_chart_script_marker(self, key: str, markers: list) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is not None:
            self._chart_script_runner.draw_markers(card, key, markers)

    @Slot(str)
    @safe_ui_action
    def _on_chart_mode_changed(self, mode_value: str) -> None:
        mode = ChartDisplayMode(mode_value)
        self._log_dev_trace("chart_mode_changed", mode=mode_value)
        self.view.set_chart_mode(mode)
        is_price_scale = mode is not ChartDisplayMode.EQUITY
        # Entry/exit PRICE markers AND the strategy indicator overlay are
        # both price-scale — meaningless, and for the overlay actively
        # harmful (drags the shared main plot's auto-range onto price
        # values), once the main plot is showing Equity instead of price.
        # See BacktestChartControls' set_trade_flags_enabled/set_ema_enabled.
        controls = self.view.chart_controls
        controls.set_trade_flags_enabled(is_price_scale)
        controls.set_ema_enabled(is_price_scale)
        self._on_ema_toggled(is_price_scale and controls.is_ema_checked())
        self._set_script_overlay_lines_visible(is_price_scale)

    @Slot(bool)
    @safe_ui_action
    def _on_ema_toggled(self, visible: bool) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is None:
            return
        for name in self._active_strategy_lines:
            card.set_indicator_visible(name, visible)

    def _set_script_overlay_lines_visible(self, visible: bool) -> None:
        """BOT-065: the reference-script counterpart to `_on_ema_toggled` —
        not the same checkbox/state (a script's line count isn't tied to
        "Chỉ báo Chiến lược" at all), but the same underlying problem: an
        overlay script left plotted through Equity-solo mode drags the
        shared main plot's auto-range onto price values, squashing the
        equity curve flat. Subplot scripts (RSI/MACD, `overlay=False`)
        don't share that plot, so they're excluded — nothing to fix for
        them."""
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is None:
            return
        for key, active in self._chart_script_runner.active.items():
            if not active.overlay:
                continue
            for line_name in active.registered_lines:
                card.set_indicator_visible(qualified_line_name(key, line_name), visible)

    @Slot()
    @safe_ui_action
    def _on_strategy_selection_changed(self) -> None:
        """A different strategy has an entirely different parameter schema —
        any values saved for the previous one would either be silently
        ignored or raise "param nobody declares" against the new one, so
        they're discarded rather than carried over (BOT-047)."""
        self._strategy_params = None
        self._view_model.set_bot_params_error("")
        self._refresh_bot_params_schema()

    @Slot(object)
    @safe_ui_action
    def _on_bot_params_save_requested(self, raw_values: dict) -> None:
        """ "Lưu & Re-Backtest" (BOT-047): validates the modal's values
        against the selected strategy's own declarations before accepting
        anything — an out-of-range/mistyped value must show an inline error
        and leave the modal open, never silently fall back to a default."""
        strategy_cls = self._strategy_registry.available().get(
            self._view_model.selectedStrategyKey
        )
        if strategy_cls is None:
            return
        try:
            parsed = parse_bot_params(strategy_cls().inputs, raw_values)
            strategy_cls(parsed)  # construct-and-discard: the real validator
        except ValueError as exc:
            self._view_model.set_bot_params_error(str(exc))
            return

        self._strategy_params = parsed
        self._view_model.set_bot_params_error("")
        self._refresh_bot_params_schema()
        self._view_model.botParamsSaved.emit()

        if self.fsm.current_state != BacktestUiState.IDLE:
            return
        config = self._build_run_config()
        if config is None:
            return
        self.fsm.transition_to(BacktestUiState.RUNNING)
        self._start_backtest_run(config)

    def _refresh_bot_params_schema(self) -> None:
        strategy_cls = self._strategy_registry.available().get(
            self._view_model.selectedStrategyKey
        )
        schema = (
            build_bot_params_schema(strategy_cls, self._strategy_params)
            if strategy_cls is not None
            else []
        )
        self._view_model.set_bot_params_schema(schema)

    @Slot()
    @safe_ui_action
    def _on_request_sync(self) -> None:
        if self._last_no_data_config is None:
            self._log_dev_trace("sync_ignored", reason="no_cached_config")
            return
        if self.fsm.current_state != BacktestUiState.IDLE:
            self._log_dev_trace("sync_ignored", state=self.fsm.current_state)
            return
        self._log_dev_trace("sync_requested")
        self.fsm.transition_to(BacktestUiState.SYNCING)
        self._view_model.set_result(_SYNCING_MESSAGE, is_error=False)
        self._log_dev_trace("sync_worker_submitted")
        self._thread_manager.submit(self._run_sync, self._last_no_data_config)

    @Slot()
    @safe_ui_action
    def _on_sync_succeeded(self) -> None:
        self._log_dev_trace("sync_succeeded")
        # Sync is just an inserted precondition, not an independent user
        # action — the user already asked to run a backtest, "no data" got
        # in the way, and now that it's synced the original intent should
        # resume automatically rather than making them click "Chạy Backtest"
        # a second time.
        self._view_model.set_needs_data_sync(False)
        cached_config = self._last_no_data_config
        self._last_no_data_config = None
        self.fsm.transition_to(BacktestUiState.RUNNING)

        # Re-read the toolbar's CURRENT config, not the cached one — the user
        # may have edited fields (symbol/strategy/range) while the sync was
        # in flight. Fall back to the config that triggered the sync only if
        # the current fields are no longer valid.
        config = self._build_run_config() or cached_config
        self._start_backtest_run(config)

    @Slot(str)
    @safe_ui_action
    def _on_sync_failed(self, message: str) -> None:
        self._log_dev_trace("sync_failed", message=message)
        # needsDataSync / _last_no_data_config are left untouched — the sync
        # that just failed was for genuinely missing data, so "Đồng bộ ngay"
        # should stay offered for the user to retry.
        self.fsm.transition_to(BacktestUiState.IDLE)
        self._view_model.set_result(f"Đồng bộ thất bại: {message}", is_error=True)

    @Slot()
    @safe_ui_action
    def _on_trade_log_query_changed(self) -> None:
        self._refresh_trade_log()

    @Slot()
    @safe_ui_action
    def _on_trade_log_export_requested(self) -> None:
        if not self._all_trades:
            return
        path, _selected_filter = QFileDialog.getSaveFileName(
            self.view,
            _EXPORT_DIALOG_TITLE,
            _EXPORT_DEFAULT_FILENAME,
            _EXPORT_FILE_FILTER,
        )
        if not path:
            return
        export_trades_to_csv(self._currently_filtered_trades(), path)

    # ================================================================== #
    # Main-thread helpers
    # ================================================================== #

    def _filtered_and_searched_trade_log_rows(self) -> list[TradeLogRow]:
        """The rows matching the CURRENT filter tab + search text, in full
        (not yet paginated) — shared by `_refresh_trade_log` (which then
        paginates) and CSV export (which doesn't)."""
        view_model = self._view_model
        rows = build_trade_log_rows(self._all_trades)
        filter_ = TradeLogFilter(view_model.tradeLogFilter)
        filtered = filter_trade_log_rows(rows, filter_)
        return search_trade_log_rows(filtered, view_model.tradeLogSearchText)

    def _currently_filtered_trades(self) -> list[Trade]:
        """The `Trade`s behind whatever's currently filtered/searched into
        view — CSV export matches what the user is looking at, not
        necessarily everything a run produced."""
        matching_indexes = {
            row.index for row in self._filtered_and_searched_trade_log_rows()
        }
        return [
            trade
            for position, trade in enumerate(self._all_trades, start=1)
            if position in matching_indexes
        ]

    def _refresh_trade_log(self) -> None:
        """Recomputes the Trade Logs table from `self._all_trades` — called
        after every run (new data) and every filter/search/page change from
        QML (`tradeLogQueryChanged`)."""
        matched = self._filtered_and_searched_trade_log_rows()
        page_rows = paginate_trade_log_rows(
            matched, self._view_model.tradeLogCurrentPage
        )
        self._view_model.set_trade_log_page_state(
            trade_log_rows_to_qml(page_rows),
            len(matched),
            total_pages(len(matched)),
        )

    def _build_run_config(self) -> BacktestRunConfig | None:
        """Reads and validates the toolbar fields. Returns `None` (having
        already reported the error) rather than raising — mirrors
        `SettingsPresenter._on_save`'s validate-before-any-side-effect shape."""
        view_model = self._view_model

        try:
            initial_balance = float(view_model.initialCapitalText)
        except ValueError:
            self._log_dev_trace(
                "run_config_invalid",
                reason="invalid_capital",
                capital=view_model.initialCapitalText,
            )
            view_model.set_result(
                _INVALID_CAPITAL_MESSAGE.format(value=view_model.initialCapitalText),
                is_error=True,
            )
            return None
        if initial_balance <= 0:
            self._log_dev_trace("run_config_invalid", reason="non_positive_capital")
            view_model.set_result(_NON_POSITIVE_CAPITAL_MESSAGE, is_error=True)
            return None

        if not view_model.selectedStrategyKey:
            self._log_dev_trace("run_config_invalid", reason="missing_strategy")
            view_model.set_result(_NO_STRATEGY_MESSAGE, is_error=True)
            return None

        preset = TimeRangePreset(view_model.timeRangePreset)
        custom_start: datetime | None = None
        custom_end: datetime | None = None
        if preset is TimeRangePreset.CUSTOM:
            custom_start = _parse_custom_datetime(view_model.customStartText)
            if custom_start is None:
                self._log_dev_trace("run_config_invalid", reason="invalid_custom_start")
                view_model.set_result(_INVALID_CUSTOM_START_MESSAGE, is_error=True)
                return None
            custom_end = _parse_custom_datetime(view_model.customEndText)
            if custom_end is not None and custom_start >= custom_end:
                self._log_dev_trace("run_config_invalid", reason="invalid_custom_range")
                view_model.set_result(_INVALID_CUSTOM_RANGE_MESSAGE, is_error=True)
                return None

        start_time, end_time = resolve_time_range(
            preset, datetime.now(UTC), custom_start, custom_end
        )

        self._log_dev_trace(
            "run_config_built",
            symbol=self._symbol,
            strategy=view_model.selectedStrategyKey,
            timeframe=view_model.selectedTimeframe,
            start=start_time,
            end=end_time,
            has_params=bool(self._strategy_params),
        )

        return BacktestRunConfig(
            strategy_key=view_model.selectedStrategyKey,
            timeframe=TimeFrame(view_model.selectedTimeframe),
            initial_balance=initial_balance,
            start_time=start_time,
            end_time=end_time,
            strategy_params=self._strategy_params,
            currency=Currency(view_model.selectedCurrency),
        )

    # ================================================================== #
    # Background method — submitted to IThreadManager.
    # MUST NOT touch the view model directly. Signals only.
    # ================================================================== #

    def _run_backtest(self, config: BacktestRunConfig) -> None:
        self._log_dev_trace(
            "worker_start",
            strategy=config.strategy_key,
            timeframe=config.timeframe.value,
        )
        try:
            command = RunStaticBacktestCommand(
                symbol=self._symbol,
                interval=config.timeframe,
                strategy_key=config.strategy_key,
                initial_balance=config.initial_balance,
                start_time=config.start_time,
                end_time=config.end_time,
                strategy_params=config.strategy_params,
            )
            self._log_dev_trace(
                "worker_dispatch_run_static_backtest",
                symbol=command.symbol,
                timeframe=command.interval.value,
            )
            result = self.dispatcher.dispatch(RunStaticBacktestCommand, command)
        except Exception as exc:
            logger.exception("Static backtest failed")
            self._log_dev_trace("worker_failed", message=str(exc))
            self._backtestFailedSignal.emit(str(exc))
            return

        if result is None:
            self._log_dev_trace("worker_no_data")
            self._backtestEmptySignal.emit(
                f"Không có dữ liệu lịch sử cho {self._symbol} "
                f"({config.timeframe.value}). Hãy sync dữ liệu trước.",
                config,
            )
            return

        self._log_dev_trace(
            "worker_result_ready",
            trades=len(result.trades),
            net_profit_percent=result.metrics.net_profit_percent,
        )
        self._fetch_and_emit_chart_data(config, result)
        # Emitted whether or not there are trades — _on_backtest_succeeded
        # always has a real BacktestResult to build stat cards from; only
        # "no historical data at all" (result is None, above) has none.
        self._backtestSucceededSignal.emit(result)

    def _run_sync(self, config: BacktestRunConfig) -> None:
        """Background worker: dispatches `SyncMarketDataCommand` for the
        symbol/timeframe/range that just came back "no data" — mirrors
        `DataManagementPresenter._run_single_sync`, minus the progress-bar
        events that screen needs and this one doesn't (one sync, one
        outcome, no multi-target loop)."""
        self._log_dev_trace(
            "sync_worker_start",
            timeframe=config.timeframe.value,
            start=config.start_time,
            end=config.end_time,
        )
        try:
            command = SyncMarketDataCommand(
                symbols=[self._symbol],
                interval=config.timeframe,
                start_time=config.start_time,
                end_time=config.end_time,
            )
            self._log_dev_trace(
                "sync_dispatch",
                symbol=self._symbol,
                timeframe=config.timeframe.value,
            )
            self.dispatcher.dispatch(SyncMarketDataCommand, command)
        except Exception as exc:
            logger.exception("Market data sync failed")
            self._log_dev_trace("sync_worker_failed", message=str(exc))
            self._syncFailedSignal.emit(str(exc))
            return
        self._syncSucceededSignal.emit()

    def _fetch_and_emit_chart_data(
        self, config: BacktestRunConfig, result: BacktestResult
    ) -> None:
        """
        @brief Separate from the BacktestResult dispatch above — the chart
        needs the raw candles too, which `RunStaticBacktestCommand` never
        returns (BOT-056 §1 finding: nothing before this task ever fetched
        them for this screen). A failure here must not undo the
        already-reported BacktestResult; it only leaves the chart empty.
        """
        try:
            query = GetHistoricalKlinesQuery(
                symbol=self._symbol,
                interval=config.timeframe.value,
                limit=_CHART_KLINES_FETCH_LIMIT,
                start_time=config.start_time,
                end_time=config.end_time,
                # Descending + reversed below (mirrors dashboard_presenter's
                # own _run_load_history) so a range with more than
                # _CHART_KLINES_FETCH_LIMIT bars keeps the MOST RECENT ones —
                # ascending order would silently cap at the OLDEST instead.
                order_by_desc=True,
            )
            self._log_dev_trace(
                "chart_query_dispatch",
                symbol=self._symbol,
                timeframe=config.timeframe.value,
                limit=_CHART_KLINES_FETCH_LIMIT,
            )
            response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            raw_klines = list(reversed(getattr(response, "data", response) or []))
        except Exception as exc:
            logger.exception("Fetching chart klines failed")
            self._log_dev_trace("chart_query_failed", message=str(exc))
            return

        if not raw_klines:
            self._log_dev_trace("chart_query_empty")
            return

        mapped_klines = map_klines(raw_klines)
        mapped_volume = map_volume(raw_klines)
        self._log_dev_trace(
            "chart_query_ready",
            raw_klines=len(raw_klines),
            mapped_klines=len(mapped_klines),
            mapped_volume=len(mapped_volume),
        )
        self._chartDataReadySignal.emit(result, mapped_klines, mapped_volume)

        self._emit_strategy_indicator_lines(config, raw_klines)

        # BOT-064: user-picked reference scripts — batch feed, same klines
        # already fetched above, entirely independent of the strategy lines
        # just emitted (self._chart_script_keys was snapshotted on the main
        # thread by _start_backtest_run before this background method ran).
        self._log_dev_trace(
            "chart_scripts_rebuild", script_keys=self._chart_script_keys
        )
        self._chart_script_runner.rebuild(self._chart_script_keys)
        self._chart_script_runner.feed_all(raw_klines)
        self._log_dev_trace("chart_scripts_fed", raw_klines=len(raw_klines))

    def _emit_strategy_indicator_lines(
        self, config: BacktestRunConfig, raw_klines: list
    ) -> None:
        """
        @brief BOT-060: draws whatever indicators the backtested strategy
        itself declares (`build_indicators()`), instead of the fixed
        `ema_ribbon` script this used to hardcode — so the chart always
        matches what actually drove that run's Buy/Sell decisions.
        @details Builds a second, throwaway strategy instance (construct-
        and-discard, same pattern `BOT-047`'s save-validation uses) purely
        to replay its indicators over the candles already fetched above —
        entirely separate from the real `StrategyEngine` run behind
        `result`, so `strategy_engine.py` stays untouched.
        """
        strategy_cls = self._strategy_registry.available().get(config.strategy_key)
        if strategy_cls is None:
            return
        strategy = strategy_cls(config.strategy_params)
        lines = compute_strategy_indicator_lines(strategy, raw_klines)
        colors = assign_strategy_line_colors(list(lines.keys()))
        for name, (x_data, y_data) in lines.items():
            self._chartStrategyLineSignal.emit(name, colors[name], x_data, y_data)
