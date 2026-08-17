from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from Sagittarius_Elite_Warrior.src.application.events.sync_events import (
    SingleSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.services.backtest_range_coverage import (
    BacktestRangeCoverage,
)
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest import (
    BacktestCancelled,
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_backtest_range_coverage import (
    GetBacktestRangeCoverageQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_toolbar import (
    DEFAULT_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import (
    DEFAULT_LOG_MAX_ENTRIES,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.indicator_script_runner import (
    IndicatorScriptRunner,
    qualified_line_name,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.kline_mapping import (
    map_klines,
    map_volume,
)
from sagittarius_engine.extensions.health.health_check_query import HealthCheckQuery
from sagittarius_engine.extensions.health.health_module import HealthUpdatedEvent
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.extensions.pyside_mvc.base_view import DEV_MODE_CONFIG_KEY
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .backtest_view_model import BackTestViewModel
from .logic.backtest_event_logger import BacktestEventLogger
from .logic.backtest_fsm_matrix import (
    BACKTEST_STATE_TRANSITIONS,
    BacktestActionContext,
    BacktestActionKind,
    BacktestActionOutcome,
    BacktestRunConfig,
    BacktestUiEvent,
    BacktestUiState,
)
from .logic.backtest_limitations_view import build_backtest_limitations
from .logic.bot_params_form import (
    build_bot_params_rows,
    build_bot_params_schema,
    parse_bot_params,
)
from .logic.chart_canvas_view import ChartDisplayMode
from .logic.performance_metrics_view import (
    build_extended_stat_cards,
    build_primary_stat_cards,
    build_result_warning_text,
    stat_cards_to_qml,
)
from .logic.pre_backtest_assertions import (
    PreBacktestAssertionPipeline,
    PreBacktestInput,
    parse_custom_datetime,
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

_NO_STRATEGY_MESSAGE = "Chưa có chiến lược nào được đăng ký."
_RUNNING_MESSAGE = "Đang chạy backtest..."
_CANCELLING_MESSAGE = "Đang hủy backtest..."
_SYNCING_MESSAGE = "Đang đồng bộ dữ liệu..."
_ZERO_TRADES_MESSAGE = (
    "Backtest chạy xong nhưng không có giao dịch nào trong khoảng thời gian đã chọn."
)

_EXPORT_DIALOG_TITLE = "Xuất Trade Logs"
_EXPORT_DEFAULT_FILENAME = "trade_logs.csv"
_EXPORT_FILE_FILTER = "CSV Files (*.csv)"

#: Preview/chart rendering is intentionally bounded; range coverage itself is
#: checked by a compact SQLite aggregate and is not inferred from this window.
_CHART_KLINES_FETCH_LIMIT = 5000

#: A kline can be closed locally yet still be absent from the exchange's
#: historical endpoint for a short publication window.  Live-ended backtests
#: therefore stop one full bar behind ``now``; this is a deterministic data
#: watermark, not a claim that the chart has no newer in-progress candle.
_LIVE_BACKTEST_END_DELAY_INTERVALS = 1


def _humanize_strategy_key(key: str) -> str:
    return key.replace("_", " ").title()


def _parse_custom_datetime(raw: str) -> datetime | None:
    """Compatibility seam; parsing belongs to BOT-095E's assertion module."""
    return parse_custom_datetime(raw)


def _published_candle_cutoff(now: datetime, timeframe: TimeFrame) -> datetime:
    """Return the latest live boundary safe for historical backtesting."""
    delay_seconds = timeframe.to_seconds() * _LIVE_BACKTEST_END_DELAY_INTERVALS
    return now - timedelta(seconds=delay_seconds)


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
    UI_TRANSITION_MATRIX = BACKTEST_STATE_TRANSITIONS

    _backtestSucceededSignal = Signal(int, object)  # action_id, BacktestResult
    _backtestEmptySignal = Signal(int, str, object)  # action_id, message, config
    _backtestFailedSignal = Signal(int, str)  # action_id, error message
    _backtestCancelledSignal = Signal(int, object)  # action_id, BacktestCancelled
    _backtestProgressSignal = Signal(int, str, int, int, float)
    _backtestCoverageMissingSignal = Signal(int, object, object, bool)
    _backtestCoverageReadySignal = Signal(int, object)
    _chartDataReadySignal = Signal(
        int, object, list, list
    )  # action_id, result, klines, volume
    # BOT-060: line_name, color, x_data, y_data — one emit per line, after
    # the whole run has been fed (same O(N) reasoning as BOT-036's feed_all).
    _chartStrategyLineSignal = Signal(int, str, str, list, list)
    # BOT-064: user-picked reference indicator scripts (RSI/MACD/...),
    # independent of the strategy's own lines above — same 4-signal shape
    # DashboardPresenter uses for IndicatorScriptRunner's 4 output channels.
    _chartScriptLineSignal = Signal(str, list, list)  # qualified name, x, y
    _chartScriptRegionSignal = Signal(str, list)  # script key, spans
    _chartScriptInfoSignal = Signal(str, list)  # script key, info fields
    _chartScriptMarkerSignal = Signal(str, list)  # script key, markers
    _syncSucceededSignal = Signal(int)  # action_id
    _syncFailedSignal = Signal(int, str)  # action_id, error message
    _syncProgressSignal = Signal(int, int, int)  # action_id, current, total
    _previewDataReadySignal = Signal(int, object, list, list)
    _uiLogSignal = Signal(str, str, bool)  # message, level, is_dev

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

        # BOT-095B: Snapshot of the last executed backtest run configuration.
        # Used for Dirty Tracking to compare against active toolbar inputs.
        self._last_run_config: BacktestRunConfig | None = None

        # BOT-095H: each background action owns one generation. A later
        # action invalidates callbacks from every earlier generation.
        self._next_action_id = 0
        self._active_action: BacktestActionContext | None = None
        self._active_action_outcome: BacktestActionOutcome | None = None
        self._backtest_cancellation_token: CancellationToken | None = None
        self._cancelling_action_id: int | None = None
        self._next_preview_id = 0
        self._active_preview_id = 0

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

        self._is_dev_mode: bool = bool(self.config.get(DEV_MODE_CONFIG_KEY, False))
        raw_max_entries = self.config.get(
            ConfigKeys.BACKTEST_LOG_MAX_ENTRIES.value, DEFAULT_LOG_MAX_ENTRIES
        )
        try:
            self._log_max_entries = (
                int(raw_max_entries)
                if not isinstance(raw_max_entries, bool)
                else DEFAULT_LOG_MAX_ENTRIES
            )
        except (ValueError, TypeError):
            self._log_max_entries = DEFAULT_LOG_MAX_ENTRIES
        self._logger = BacktestEventLogger(
            log_model=self._view_model.log_model,
            is_dev_mode=self._is_dev_mode,
            emit_signal=self._emit_ui_log,
            max_entries=self._log_max_entries,
        )
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
            self.fsm.add_global_callback(self._on_fsm_state_changed)
            self._view_model.set_ui_mode(self.fsm.current_state.value)

        # Must be called explicitly at the end of __init__ per BasePresenter
        # contract, and before load_qml() so QML parses against a ready model.
        self._connect_ui_signals()
        self._connect_engine_events()
        self._trigger_initial_health_check()

        # After render_symbol_cards(): view.chart_controls doesn't exist
        # until the ChartCard it's attached to has been built.
        view.set_chart_dev_mode(self._is_dev_mode)
        view.set_chart_opengl_enabled(
            bool(
                self.config.get(
                    ConfigKeys.BACKTEST_CHART_OPENGL_ENABLED.value,
                    False,
                )
            )
        )
        view.set_chart_cached_interaction_enabled(
            bool(
                self.config.get(
                    ConfigKeys.BACKTEST_CHART_CACHED_INTERACTION_ENABLED.value,
                    True,
                )
            )
        )
        view.render_symbol_cards([self._symbol])
        self._connect_chart_controls()
        view.load_qml()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        self._view_model.runBacktestRequested.connect(self._on_run_backtest)
        self._view_model.cancelBacktestRequested.connect(self._on_cancel_backtest)
        self._view_model.syncRequested.connect(self._on_request_sync)
        self._view_model.selectedStrategyKeyChanged.connect(
            self._on_strategy_selection_changed
        )
        self._view_model.selectedTimeframeChanged.connect(self._on_timeframe_changed)
        self._view_model.timeRangePresetChanged.connect(self._on_time_range_changed)
        self._view_model.displayTimezoneChanged.connect(
            self._on_display_timezone_changed
        )
        self._view_model.customStartTextChanged.connect(self._on_custom_time_changed)
        self._view_model.customEndTextChanged.connect(self._on_custom_time_changed)
        self._view_model.initialCapitalTextChanged.connect(self._on_capital_changed)
        self._view_model.capitalValidationRequested.connect(
            self._on_capital_validation_requested
        )
        self._view_model.selectedCurrencyChanged.connect(self._on_capital_changed)
        self._view_model.script_model.enabledKeysChanged.connect(
            self._on_indicator_script_selection_changed
        )
        self._view_model.botParamsSaveRequested.connect(
            self._on_bot_params_save_requested
        )
        self._backtestSucceededSignal.connect(self._on_backtest_succeeded_for_action)
        self._backtestEmptySignal.connect(self._on_backtest_empty_for_action)
        self._backtestFailedSignal.connect(self._on_backtest_failed_for_action)
        self._backtestCancelledSignal.connect(self._on_backtest_cancelled_for_action)
        self._backtestProgressSignal.connect(self._on_backtest_progress_for_action)
        self._backtestCoverageMissingSignal.connect(
            self._on_backtest_coverage_missing_for_action
        )
        self._backtestCoverageReadySignal.connect(
            self._on_backtest_coverage_ready_for_action
        )
        self._chartDataReadySignal.connect(self._on_chart_data_ready_for_action)
        self._chartStrategyLineSignal.connect(self._on_chart_strategy_line_for_action)
        self._chartScriptLineSignal.connect(self._on_chart_script_line)
        self._chartScriptRegionSignal.connect(self._on_chart_script_region)
        self._chartScriptInfoSignal.connect(self._on_chart_script_info)
        self._chartScriptMarkerSignal.connect(self._on_chart_script_marker)
        self._syncSucceededSignal.connect(self._on_sync_succeeded_for_action)
        self._syncFailedSignal.connect(self._on_sync_failed_for_action)
        self._syncProgressSignal.connect(self._on_sync_progress_for_action)
        self._previewDataReadySignal.connect(self._on_preview_data_ready)
        self._uiLogSignal.connect(self._on_ui_log)
        self._view_model.tradeLogQueryChanged.connect(self._on_trade_log_query_changed)
        self._view_model.tradeLogExportRequested.connect(
            self._on_trade_log_export_requested
        )

    def _connect_engine_events(self) -> None:
        """Subscribe to Engine EventBus events emitted from background handlers (Observer Pattern)."""
        self.event_bus.on(BacktestCompletedEvent, self._handle_backtest_completed_event)
        self.event_bus.on(BacktestFailedEvent, self._handle_backtest_failed_event)
        self.event_bus.on(SignalGeneratedEvent, self._handle_signal_generated_event)
        self.event_bus.on(SingleSyncProgressEvent, self._handle_sync_progress_event)
        self.event_bus.on(
            HealthUpdatedEvent.event_name, self._handle_health_updated_event
        )

    def _trigger_initial_health_check(self) -> None:
        """Trigger an initial health check when backtest screen initializes."""
        try:
            health_query = self.container.resolve(HealthCheckQuery)
            status = health_query.execute()
            self._handle_health_updated_event(HealthUpdatedEvent(status))
        except Exception:  # noqa: BLE001, S110
            pass

    def _handle_health_updated_event(self, event: Any) -> None:
        status_dict = getattr(event, "status", {})
        status_str = status_dict.get("status", "unknown").upper()
        components = status_dict.get("components", {})
        db_stat = components.get("database", "ok").upper()
        bus_stat = components.get("event_bus", "ok").upper()
        self._emit_ui_log(
            f"[Health] Trạng thái hệ thống: {status_str} (Database: {db_stat}, EventBus: {bus_stat})",
            "info",
            is_dev=False,
        )

    def _handle_backtest_completed_event(self, event: BacktestCompletedEvent) -> None:
        result = getattr(event, "result", None)
        trades_count = len(result.trades) if result and hasattr(result, "trades") else 0
        duration = getattr(result, "duration", 0.0) if result else 0.0
        self._emit_ui_log(
            f"[EventBus] Backtest hoàn tất: {trades_count} lệnh (thời gian: {duration:.2f}s)",
            "info",
            is_dev=True,
        )

    def _handle_backtest_failed_event(self, event: BacktestFailedEvent) -> None:
        reason = getattr(event, "reason", str(event))
        self._emit_ui_log(
            f"[EventBus] Backtest thất bại: {reason}",
            "error",
            is_dev=False,
        )

    def _handle_signal_generated_event(self, event: SignalGeneratedEvent) -> None:
        sig = getattr(event, "signal", None)
        symbol = getattr(sig, "symbol", "") if sig else ""
        side = getattr(sig, "side", "") if sig else ""
        price = getattr(sig, "price", 0.0) if sig else 0.0
        self._emit_ui_log(
            f"[Signal] Tín hiệu: {str(side).upper()} {symbol} @ {price:,.2f}",
            "info",
            is_dev=True,
        )

    def _handle_sync_progress_event(self, event: SingleSyncProgressEvent) -> None:
        action_id = self._current_action_id(BacktestActionKind.SYNC)
        if action_id is not None:
            self._syncProgressSignal.emit(action_id, event.current, event.total)

    def _emit_ui_log(
        self, message: str, level: str = "info", is_dev: bool = False
    ) -> None:
        self._uiLogSignal.emit(message, level, is_dev)

    @Slot(str, str, bool)
    def _on_ui_log(self, message: str, level: str, is_dev: bool) -> None:
        if is_dev and not self._is_dev_mode:
            return
        self._view_model.log_model.append(message, level=level)
        count = self._view_model.log_model.rowCount()
        if not isinstance(count, int) or isinstance(count, bool):
            return
        while count > self._log_max_entries:
            self._view_model.log_model.beginRemoveRows(QModelIndex(), 0, 0)
            if (
                hasattr(self._view_model.log_model, "_entries")
                and self._view_model.log_model._entries
            ):
                self._view_model.log_model._entries.pop(0)
            self._view_model.log_model.endRemoveRows()
            count = self._view_model.log_model.rowCount()
            if not isinstance(count, int) or isinstance(count, bool):
                break

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
        self._logger.dev_trace(action, **fields)

    # ================================================================== #
    # Qt Slots — main thread
    # ================================================================== #

    def _on_fsm_state_changed(
        self, old_state: BacktestUiState, new_state: BacktestUiState
    ) -> None:
        self._view_model.set_ui_mode(new_state.value)

    def _begin_action(
        self,
        kind: BacktestActionKind,
        config: BacktestRunConfig,
        previous_state: BacktestUiState,
    ) -> BacktestActionContext:
        """Create the immutable owner record before background submission."""
        if self._active_action is not None:
            self._log_dev_trace(
                "action_superseded",
                action_id=self._active_action.action_id,
                kind=self._active_action.kind.value,
                outcome=(
                    self._active_action_outcome.value
                    if self._active_action_outcome is not None
                    else None
                ),
            )
            if self._active_action_outcome is BacktestActionOutcome.PENDING:
                self._finish_action(
                    self._active_action.action_id, BacktestActionOutcome.INVALIDATED
                )
        self._next_action_id += 1
        context = BacktestActionContext(
            action_id=self._next_action_id,
            kind=kind,
            config=deepcopy(config),
            started_at=datetime.now(UTC),
            previous_state=previous_state,
        )
        self._active_action = context
        self._active_action_outcome = BacktestActionOutcome.PENDING
        self._log_dev_trace(
            "action_started",
            action_id=context.action_id,
            kind=context.kind.value,
            config=context.config.to_summary_label(),
            previous_state=context.previous_state.value,
        )
        return context

    def _is_current_action(self, action_id: int, kind: BacktestActionKind) -> bool:
        return (
            self._active_action is not None
            and self._active_action.action_id == action_id
            and self._active_action.kind is kind
        )

    def _is_current_pending_action(
        self, action_id: int, kind: BacktestActionKind
    ) -> bool:
        return self._is_current_action(action_id, kind) and (
            self._active_action_outcome is BacktestActionOutcome.PENDING
        )

    def _current_action_id(self, kind: BacktestActionKind) -> int | None:
        if self._active_action is not None and self._active_action.kind is kind:
            return self._active_action.action_id
        return None

    def _finish_action(self, action_id: int, outcome: BacktestActionOutcome) -> None:
        if self._active_action is None or self._active_action.action_id != action_id:
            return
        self._active_action_outcome = outcome
        self._log_dev_trace(
            "action_finished",
            action_id=action_id,
            kind=self._active_action.kind.value,
            outcome=outcome.value,
        )

    def _invalidate_active_action(self) -> None:
        """Invalidate a pending action without assigning a replacement.

        BOT-095C's cancel flow will call this before requesting cooperative
        worker cancellation, so late callbacks are fenced immediately.
        """
        if (
            self._active_action is not None
            and self._active_action_outcome is BacktestActionOutcome.PENDING
        ):
            self._finish_action(
                self._active_action.action_id, BacktestActionOutcome.INVALIDATED
            )

    def _ignore_stale_action_callback(
        self, callback: str, action_id: int, kind: BacktestActionKind
    ) -> None:
        self._log_dev_trace(
            "action_callback_ignored",
            callback=callback,
            action_id=action_id,
            kind=kind.value,
            active_action_id=(
                self._active_action.action_id if self._active_action else None
            ),
            active_outcome=(
                self._active_action_outcome.value
                if self._active_action_outcome is not None
                else None
            ),
        )

    def _get_current_config(self) -> BacktestRunConfig:
        timeframe_str = self._view_model.selectedTimeframe
        try:
            tf = TimeFrame(timeframe_str)
        except ValueError:
            tf = TimeFrame.M1

        try:
            balance = float(self._view_model.initialCapitalText)
        except (ValueError, TypeError):
            balance = 10000.0

        try:
            currency = Currency(self._view_model.selectedCurrency)
        except ValueError:
            currency = Currency.USD

        preset = self._view_model.timeRangePreset
        if preset == TimeRangePreset.CUSTOM.value:
            start_dt = _parse_custom_datetime(self._view_model.customStartText)
            end_dt = _parse_custom_datetime(self._view_model.customEndText)
        else:
            try:
                start_dt, end_dt = resolve_time_range(
                    TimeRangePreset(preset), datetime.now(UTC)
                )
            except ValueError:
                start_dt, end_dt = None, None

        return BacktestRunConfig(
            strategy_key=self._view_model.selectedStrategyKey,
            timeframe=tf,
            initial_balance=balance,
            start_time=start_dt,
            end_time=end_dt,
            strategy_params=self._strategy_params,
            currency=currency,
            symbol=self._symbol,
        )

    def _on_config_input_changed(self) -> None:
        """Dirty Tracking (BOT-095B): Compares active toolbar inputs against
        the last executed run snapshot (_last_run_config) to detect stale state."""
        if self.fsm is None:
            return

        if self.fsm.current_state in (
            BacktestUiState.RUNNING,
            BacktestUiState.CANCELLING,
            BacktestUiState.SYNCING,
        ):
            return

        current_config = self._get_current_config()

        if self._last_run_config is None:
            if self.fsm.can_dispatch(BacktestUiEvent.CONFIG_CHANGED):
                self.fsm.dispatch(BacktestUiEvent.CONFIG_CHANGED)
            return

        if current_config == self._last_run_config:
            self._view_model.configDiffSummary = ""
            if self.fsm.can_dispatch(BacktestUiEvent.CONFIG_RESTORED):
                self.fsm.dispatch(BacktestUiEvent.CONFIG_RESTORED)
        else:
            diff_msg = self._last_run_config.compute_diff_summary(current_config)
            self._view_model.configDiffSummary = diff_msg
            if self.fsm.can_dispatch(BacktestUiEvent.CONFIG_CHANGED):
                self.fsm.dispatch(BacktestUiEvent.CONFIG_CHANGED)

    @Slot()
    @safe_ui_action
    def _on_run_backtest(self) -> None:
        if not self.fsm.can_dispatch(BacktestUiEvent.RUN_REQUESTED):
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
        self._logger.log_backtest_started(
            strategy_name=self._view_model.selectedStrategyName
            or self._view_model.selectedStrategyKey,
            timeframe=self._view_model.selectedTimeframe,
            capital=float(self._view_model.initialCapitalText or 0),
            currency=self._view_model.selectedCurrency,
            symbol=self._symbol,
        )
        previous_state = self.fsm.current_state
        self.fsm.dispatch(BacktestUiEvent.RUN_REQUESTED)
        self._log_dev_trace("run_transitioned", state=self.fsm.current_state)
        self._start_backtest_run(config, previous_state)

    def _start_backtest_run(
        self,
        config: BacktestRunConfig,
        previous_state: BacktestUiState | None = None,
        allow_auto_sync: bool = True,
    ) -> None:
        """Shared by the "Chạy Backtest" click and the post-sync auto-resubmit
        (`_on_sync_succeeded`) — callers are responsible for their own FSM
        transition into RUNNING first (IDLE->RUNNING vs SYNCING->RUNNING are
        different edges), this only does the actual submit."""
        if config.end_time is None:
            config = replace(
                config,
                end_time=_published_candle_cutoff(datetime.now(UTC), config.timeframe),
            )
        self._active_preview_id = 0
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

        self._backtest_cancellation_token = CancellationToken()
        self._cancelling_action_id = None
        self._view_model.reset_backtest_progress()
        action = self._begin_action(
            BacktestActionKind.BACKTEST,
            config,
            previous_state or self.fsm.current_state,
        )
        self._view_model.reset_sync_progress()
        self._view_model.set_result(_RUNNING_MESSAGE, is_error=False)
        self._log_dev_trace("run_worker_submitted")
        self._thread_manager.submit(
            self._run_backtest,
            action.config,
            action.action_id,
            self._backtest_cancellation_token,
            allow_auto_sync,
        )

    @Slot(int, object, object, bool)
    @safe_ui_action
    def _on_backtest_coverage_missing_for_action(
        self,
        action_id: int,
        config: BacktestRunConfig,
        coverage: BacktestRangeCoverage,
        allow_auto_sync: bool,
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "coverage_missing", action_id, BacktestActionKind.BACKTEST
            )
            return
        message = self._format_coverage_message(coverage)
        self._last_no_data_config = config
        self._view_model.set_data_coverage(False, message)
        self._view_model.set_needs_data_sync(True)
        self._finish_action(action_id, BacktestActionOutcome.EMPTY)
        if allow_auto_sync:
            if self.fsm.can_dispatch(BacktestUiEvent.BACKTEST_EMPTY):
                self.fsm.dispatch(BacktestUiEvent.BACKTEST_EMPTY)
            self._start_sync_for_config(config)
            return
        self._on_backtest_failed(message)

    @Slot(int, object)
    @safe_ui_action
    def _on_backtest_coverage_ready_for_action(
        self, action_id: int, coverage: BacktestRangeCoverage
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            return
        self._view_model.set_data_coverage(True, "")
        self._view_model.set_needs_data_sync(False)

    @staticmethod
    def _format_coverage_message(coverage: BacktestRangeCoverage) -> str:
        if coverage.missing_open_times:
            return f"Thiếu nến từ {coverage.missing_open_times[0]:%Y-%m-%d %H:%M UTC}."
        if coverage.duplicate_candles:
            return f"Dữ liệu có {coverage.duplicate_candles} nến trùng thời điểm."
        if coverage.has_unclosed_candle:
            return "Khoảng dữ liệu chứa nến chưa đóng."
        return "Dữ liệu local chưa đủ cho khoảng Backtest đã chọn."

    @Slot()
    @safe_ui_action
    def _on_cancel_backtest(self) -> None:
        action_id = self._current_action_id(BacktestActionKind.BACKTEST)
        if (
            action_id is None
            or not self._is_current_pending_action(
                action_id, BacktestActionKind.BACKTEST
            )
            or not self.fsm.can_dispatch(BacktestUiEvent.CANCEL_REQUESTED)
        ):
            self._log_dev_trace("cancel_ignored", state=self.fsm.current_state)
            return

        self._cancelling_action_id = action_id
        self._invalidate_active_action()
        self.fsm.dispatch(BacktestUiEvent.CANCEL_REQUESTED)
        if self._backtest_cancellation_token is not None:
            self._backtest_cancellation_token.cancel()
        self._view_model.set_result(_CANCELLING_MESSAGE, is_error=False)
        self._emit_ui_log("Đang gửi yêu cầu hủy Backtest...", "info")
        self._log_dev_trace("cancel_requested", action_id=action_id)

    def _is_cancelling_action(self, action_id: int) -> bool:
        return (
            self._is_current_action(action_id, BacktestActionKind.BACKTEST)
            and self._active_action_outcome is BacktestActionOutcome.INVALIDATED
            and self._cancelling_action_id == action_id
            and self.fsm.current_state is BacktestUiState.CANCELLING
        )

    def _cancel_restore_event(self, previous_state: BacktestUiState) -> BacktestUiEvent:
        if previous_state is BacktestUiState.CONFIG_DIRTY:
            return BacktestUiEvent.BACKTEST_CANCELLED_TO_CONFIG_DIRTY
        if previous_state is BacktestUiState.COMPLETED:
            return BacktestUiEvent.BACKTEST_CANCELLED_TO_COMPLETED
        return BacktestUiEvent.BACKTEST_CANCELLED

    def _complete_cancelled_action(self, action_id: int) -> None:
        if not self._is_cancelling_action(action_id) or self._active_action is None:
            self._ignore_stale_action_callback(
                "backtest_cancelled", action_id, BacktestActionKind.BACKTEST
            )
            return
        previous_state = self._active_action.previous_state
        self._finish_action(action_id, BacktestActionOutcome.CANCELLED)
        self._cancelling_action_id = None
        self._backtest_cancellation_token = None
        self._view_model.reset_backtest_progress()
        self._view_model.set_result(
            "Đã hủy Backtest. Kết quả trước đó được giữ nguyên.", is_error=False
        )
        self._emit_ui_log("Đã hủy Backtest. Kết quả trước đó được giữ nguyên.", "info")
        event = self._cancel_restore_event(previous_state)
        if self.fsm.can_dispatch(event):
            self.fsm.dispatch(event)
        self._log_dev_trace(
            "cancel_completed", action_id=action_id, restore_state=previous_state.value
        )

    @Slot(int, object)
    @safe_ui_action
    def _on_backtest_succeeded_for_action(
        self, action_id: int, result: BacktestResult
    ) -> None:
        if self._is_cancelling_action(action_id):
            self._complete_cancelled_action(action_id)
            return
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "backtest_succeeded", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_backtest_succeeded(result)
        self._finish_action(action_id, BacktestActionOutcome.SUCCEEDED)

    @Slot(int, str, object)
    @safe_ui_action
    def _on_backtest_empty_for_action(
        self, action_id: int, message: str, config: BacktestRunConfig
    ) -> None:
        if self._is_cancelling_action(action_id):
            self._complete_cancelled_action(action_id)
            return
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "backtest_empty", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_backtest_empty(message, config)
        self._finish_action(action_id, BacktestActionOutcome.EMPTY)

    @Slot(int, str)
    @safe_ui_action
    def _on_backtest_failed_for_action(self, action_id: int, message: str) -> None:
        if self._is_cancelling_action(action_id):
            self._complete_cancelled_action(action_id)
            return
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "backtest_failed", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_backtest_failed(message)
        self._finish_action(action_id, BacktestActionOutcome.FAILED)

    @Slot(int, object)
    @safe_ui_action
    def _on_backtest_cancelled_for_action(
        self, action_id: int, outcome: BacktestCancelled
    ) -> None:
        if not self._is_cancelling_action(action_id):
            self._ignore_stale_action_callback(
                "backtest_cancelled", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._log_dev_trace(
            "worker_cancelled",
            action_id=action_id,
            phase=outcome.phase,
            processed=outcome.processed_bars,
            total=outcome.total_bars,
        )
        self._complete_cancelled_action(action_id)

    @Slot(int, str, int, int, float)
    @safe_ui_action
    def _on_backtest_progress_for_action(
        self,
        action_id: int,
        phase: str,
        completed_bars: int,
        total_bars: int,
        elapsed_seconds: float,
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            return
        if total_bars <= 0:
            return
        percent = min(100.0, max(0.0, completed_bars / total_bars * 100.0))
        eta_seconds = (
            max(
                0,
                round(elapsed_seconds * (total_bars - completed_bars) / completed_bars),
            )
            if completed_bars > 0
            else None
        )
        phase_label = {
            "in_sample": "Kiểm tra in-sample",
            "out_of_sample": "Kiểm tra out-of-sample",
            "full": "Chạy toàn bộ dữ liệu",
        }.get(phase, "Đang chạy")
        eta_label = f" · ETA ~{eta_seconds}s" if eta_seconds is not None else ""
        self._view_model.set_backtest_progress(
            percent, f"{phase_label}: {percent:.0f}%{eta_label}"
        )

    @Slot(int, object, list, list)
    @safe_ui_action
    def _on_chart_data_ready_for_action(
        self, action_id: int, result: BacktestResult, klines: list, volume: list
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "chart_data_ready", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_chart_data_ready(result, klines, volume)

    @Slot(int, str, str, list, list)
    @safe_ui_action
    def _on_chart_strategy_line_for_action(
        self, action_id: int, name: str, color: str, x_data: list, y_data: list
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "chart_strategy_line", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_chart_strategy_line(name, color, x_data, y_data)

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
        duration_sec = getattr(result, "duration", 0.0)
        net_profit = result.metrics.net_profit if result.metrics else 0.0
        win_rate = result.metrics.percent_profitable if result.metrics else 0.0
        self._logger.log_backtest_completed(
            duration_sec=duration_sec,
            trade_count=len(result.trades),
            net_pnl=net_profit,
            win_rate=win_rate,
            currency=self._view_model.selectedCurrency,
        )
        self._last_run_config = self._get_current_config()
        self._view_model.lastRunSummary = self._last_run_config.to_summary_label()
        self._view_model.configDiffSummary = ""
        if self.fsm.can_dispatch(BacktestUiEvent.BACKTEST_SUCCEEDED):
            self.fsm.dispatch(BacktestUiEvent.BACKTEST_SUCCEEDED)

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
        self._logger.log_backtest_empty(message)
        if self.fsm.can_dispatch(BacktestUiEvent.BACKTEST_EMPTY):
            self.fsm.dispatch(BacktestUiEvent.BACKTEST_EMPTY)
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
        self._logger.log_backtest_failed(message)
        if self.fsm.can_dispatch(BacktestUiEvent.BACKTEST_FAILED):
            self.fsm.dispatch(BacktestUiEvent.BACKTEST_FAILED)

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
        self._logger.log_klines_loaded(len(klines), self._symbol)
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
        self._logger.log_strategy_selected(
            self._view_model.selectedStrategyName,
            self._view_model.selectedStrategyKey,
        )
        self._on_config_input_changed()

    @Slot()
    @safe_ui_action
    def _on_timeframe_changed(self) -> None:
        self._logger.log_timeframe_selected(self._view_model.selectedTimeframe)
        self._on_config_input_changed()
        self._request_chart_preview()

    @Slot()
    @safe_ui_action
    def _on_time_range_changed(self) -> None:
        self._logger.log_time_range_selected(
            self._view_model.timeRangePreset,
            self._view_model.customStartText,
            self._view_model.customEndText,
        )
        self._on_config_input_changed()
        self._request_chart_preview()

    @Slot()
    @safe_ui_action
    def _on_custom_time_changed(self) -> None:
        if self._view_model.timeRangePreset == TimeRangePreset.CUSTOM.value:
            self._on_config_input_changed()
            self._request_chart_preview()

    def _request_chart_preview(self) -> None:
        """Probe and preview a toolbar range without blocking the Qt thread."""
        if self.fsm.current_state in (
            BacktestUiState.RUNNING,
            BacktestUiState.CANCELLING,
            BacktestUiState.SYNCING,
        ):
            return
        config = self._get_current_config()
        if self._view_model.timeRangePreset == TimeRangePreset.CUSTOM.value:
            if config.start_time is None or config.end_time is None:
                return
            if config.start_time >= config.end_time:
                return
        self._next_preview_id += 1
        self._active_preview_id = self._next_preview_id
        self._thread_manager.submit(
            self._run_chart_preview,
            config,
            self._active_preview_id,
        )

    def _run_chart_preview(self, config: BacktestRunConfig, preview_id: int) -> None:
        """Background preview query; generation ID fences rapid toolbar changes."""
        now = datetime.now(UTC)
        try:
            query = GetHistoricalKlinesQuery(
                symbol=self._symbol,
                interval=config.timeframe.value,
                limit=_CHART_KLINES_FETCH_LIMIT,
                start_time=config.start_time,
                end_time=config.end_time or now,
                order_by_desc=True,
            )
            response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            raw_klines = list(reversed(list(getattr(response, "data", response) or [])))
            coverage = self.dispatcher.dispatch(
                GetBacktestRangeCoverageQuery,
                GetBacktestRangeCoverageQuery(
                    symbol=self._symbol,
                    interval=config.timeframe.value,
                    start_time=config.start_time,
                    end_time=config.end_time or now,
                    now=now,
                ),
            )
            self._previewDataReadySignal.emit(
                preview_id,
                coverage,
                map_klines(raw_klines),
                map_volume(raw_klines),
            )
        except Exception as exc:
            logger.exception("Fetching Backtest chart preview failed")
            self._log_dev_trace("preview_query_failed", message=str(exc))

    @Slot(int, object, list, list)
    @safe_ui_action
    def _on_preview_data_ready(
        self,
        preview_id: int,
        coverage: BacktestRangeCoverage,
        klines: list,
        volume: list,
    ) -> None:
        if preview_id != self._active_preview_id:
            self._log_dev_trace("preview_ignored", preview_id=preview_id)
            return
        self._view_model.set_data_coverage(
            coverage.is_fully_covered,
            ""
            if coverage.is_fully_covered
            else self._format_coverage_message(coverage),
        )
        self._view_model.set_needs_data_sync(not coverage.is_fully_covered)
        self.view.on_preview_data_ready(klines, volume)

    @Slot()
    @safe_ui_action
    def _on_capital_changed(self) -> None:
        self._set_capital_validation_message(self._view_model.initialCapitalText)
        try:
            capital_val = float(self._view_model.initialCapitalText)
            self._logger.log_capital_updated(
                capital_val,
                self._view_model.selectedCurrency,
            )
        except (ValueError, TypeError):
            pass
        self._on_config_input_changed()

    @Slot(str)
    @safe_ui_action
    def _on_capital_validation_requested(self, value: str) -> None:
        self._set_capital_validation_message(value)

    def _set_capital_validation_message(self, value: str) -> None:
        issues = PreBacktestAssertionPipeline.default().validate(
            PreBacktestInput(value, False, "", "")
        )
        self._view_model.set_capital_validation_message(
            issues[0].message if issues else ""
        )

    @Slot()
    @safe_ui_action
    def _on_indicator_script_selection_changed(self) -> None:
        enabled_keys = sorted(self._view_model.script_model.enabled_keys)
        scripts_str = ", ".join(enabled_keys) if enabled_keys else "Không có"
        self._logger.info(f"Đã cập nhật chỉ báo tham chiếu: {scripts_str}")

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
        self._logger.log_bot_params_saved(
            self._view_model.selectedStrategyName,
            parsed,
        )
        self._on_config_input_changed()

        if not self.fsm.can_dispatch(BacktestUiEvent.RUN_REQUESTED):
            return
        config = self._build_run_config()
        if config is None:
            return
        previous_state = self.fsm.current_state
        self.fsm.dispatch(BacktestUiEvent.RUN_REQUESTED)
        self._start_backtest_run(config, previous_state)

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
        self._view_model.set_bot_params_rows(build_bot_params_rows(schema))

    @Slot()
    @safe_ui_action
    def _on_request_sync(self) -> None:
        if self._last_no_data_config is None:
            self._log_dev_trace("sync_ignored", reason="no_cached_config")
            return
        if not self.fsm.can_dispatch(BacktestUiEvent.SYNC_REQUESTED):
            self._log_dev_trace("sync_ignored", state=self.fsm.current_state)
            return
        self._start_sync_for_config(self._last_no_data_config)

    def _start_sync_for_config(self, sync_config: BacktestRunConfig) -> None:
        if not self.fsm.can_dispatch(BacktestUiEvent.SYNC_REQUESTED):
            self._log_dev_trace("sync_ignored", state=self.fsm.current_state)
            return
        self._log_dev_trace("sync_requested")
        previous_state = self.fsm.current_state
        self.fsm.dispatch(BacktestUiEvent.SYNC_REQUESTED)
        action = self._begin_action(
            BacktestActionKind.SYNC, sync_config, previous_state
        )
        self._view_model.set_result(_SYNCING_MESSAGE, is_error=False)
        self._log_dev_trace("sync_worker_submitted")
        self._thread_manager.submit(self._run_sync, action.config, action.action_id)

    @Slot(int, int, int)
    @safe_ui_action
    def _on_sync_progress_for_action(
        self, action_id: int, current: int, total: int
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.SYNC):
            return
        percent = min(100.0, max(0.0, current / total * 100.0)) if total > 0 else 0.0
        self._view_model.set_sync_progress(
            percent,
            f"Đang đồng bộ nến: {current:,}/{total:,} ({percent:.0f}%)",
        )

    @Slot(int)
    @safe_ui_action
    def _on_sync_succeeded_for_action(self, action_id: int) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.SYNC):
            self._ignore_stale_action_callback(
                "sync_succeeded", action_id, BacktestActionKind.SYNC
            )
            return
        self._finish_action(action_id, BacktestActionOutcome.SUCCEEDED)
        self._on_sync_succeeded()

    @Slot(int, str)
    @safe_ui_action
    def _on_sync_failed_for_action(self, action_id: int, message: str) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.SYNC):
            self._ignore_stale_action_callback(
                "sync_failed", action_id, BacktestActionKind.SYNC
            )
            return
        self._on_sync_failed(message)
        self._finish_action(action_id, BacktestActionOutcome.FAILED)

    @Slot()
    @safe_ui_action
    def _on_sync_succeeded(self) -> None:
        self._log_dev_trace("sync_succeeded")
        self._logger.log_sync_event("Đồng bộ dữ liệu thành công.")
        self._view_model.reset_sync_progress()
        # Sync is just an inserted precondition, not an independent user
        # action — the user already asked to run a backtest, "no data" got
        # in the way, and now that it's synced the original intent should
        # resume automatically rather than making them click "Chạy Backtest"
        # a second time.
        cached_config = self._last_no_data_config
        self._view_model.set_needs_data_sync(False)
        self._last_no_data_config = None
        if self.fsm.can_dispatch(BacktestUiEvent.SYNC_SUCCEEDED):
            self.fsm.dispatch(BacktestUiEvent.SYNC_SUCCEEDED)

        # The sync authorizes only the original run intent. A later task may
        # allow edits/cancel while syncing, but it must invalidate this action
        # rather than letting a stale sync infer a fresh intent from toolbar
        # values.
        if cached_config is not None:
            self._start_backtest_run(cached_config, allow_auto_sync=False)

    @Slot(str)
    @safe_ui_action
    def _on_sync_failed(self, message: str) -> None:
        self._log_dev_trace("sync_failed", message=message)
        self._logger.log_sync_event(f"Đồng bộ thất bại: {message}", is_error=True)
        self._view_model.reset_sync_progress()
        # needsDataSync / _last_no_data_config are left untouched — the sync
        # that just failed was for genuinely missing data, so "Đồng bộ ngay"
        # should stay offered for the user to retry.
        if self.fsm.can_dispatch(BacktestUiEvent.SYNC_FAILED):
            self.fsm.dispatch(BacktestUiEvent.SYNC_FAILED)
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
        if self._view_model.isConfigDirty:
            self._logger.info(
                f"Đang xuất Trade Logs của lần chạy trước ({self._view_model.lastRunSummary})."
            )
        path, _selected_filter = QFileDialog.getSaveFileName(
            self.view,
            _EXPORT_DIALOG_TITLE,
            _EXPORT_DEFAULT_FILENAME,
            _EXPORT_FILE_FILTER,
        )
        if not path:
            return
        export_trades_to_csv(self._currently_filtered_trades(), path)

    @Slot()
    @safe_ui_action
    def _on_display_timezone_changed(self) -> None:
        """Propagates display timezone change to the chart and re-renders trade log table without dirtying config."""
        tz_name = self._view_model.displayTimezone
        self.view.set_display_timezone(tz_name)
        self._refresh_trade_log()

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
            trade_log_rows_to_qml(page_rows, tz_name=self._view_model.displayTimezone),
            len(matched),
            total_pages(len(matched)),
        )

    def _build_run_config(self) -> BacktestRunConfig | None:
        """Reads and validates the toolbar fields. Returns `None` (having
        already reported the error) rather than raising — mirrors
        `SettingsPresenter._on_save`'s validate-before-any-side-effect shape."""
        view_model = self._view_model

        preset = TimeRangePreset(view_model.timeRangePreset)
        assertions = PreBacktestAssertionPipeline.default().validate(
            PreBacktestInput(
                capital_text=view_model.initialCapitalText,
                is_custom_range=preset is TimeRangePreset.CUSTOM,
                custom_start_text=view_model.customStartText,
                custom_end_text=view_model.customEndText,
            )
        )
        if assertions:
            issue = assertions[0]
            self._log_dev_trace(
                "run_config_invalid",
                reason=issue.field.value,
                capital=view_model.initialCapitalText,
            )
            view_model.set_result(issue.message, is_error=True)
            return None

        initial_balance = float(view_model.initialCapitalText)

        if not view_model.selectedStrategyKey:
            self._log_dev_trace("run_config_invalid", reason="missing_strategy")
            view_model.set_result(_NO_STRATEGY_MESSAGE, is_error=True)
            return None

        custom_start: datetime | None = None
        custom_end: datetime | None = None
        if preset is TimeRangePreset.CUSTOM:
            custom_start = _parse_custom_datetime(view_model.customStartText)
            custom_end = _parse_custom_datetime(view_model.customEndText)

        range_now = datetime.now(UTC)
        if preset is not TimeRangePreset.CUSTOM:
            range_now = _published_candle_cutoff(
                range_now, TimeFrame(view_model.selectedTimeframe)
            )
        start_time, end_time = resolve_time_range(
            preset, range_now, custom_start, custom_end
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

    def _run_backtest(
        self,
        config: BacktestRunConfig,
        action_id: int | None = None,
        cancellation_token: CancellationToken | None = None,
        allow_auto_sync: bool = False,
    ) -> None:
        resolved_action_id = action_id or self._current_action_id(
            BacktestActionKind.BACKTEST
        )
        if resolved_action_id is None:
            return
        self._log_dev_trace(
            "worker_start",
            action_id=resolved_action_id,
            strategy=config.strategy_key,
            timeframe=config.timeframe.value,
        )
        try:
            if cancellation_token is not None:
                coverage = self._probe_data_coverage(config)
                if not coverage.is_fully_covered:
                    self._backtestCoverageMissingSignal.emit(
                        resolved_action_id, config, coverage, allow_auto_sync
                    )
                    return
                self._backtestCoverageReadySignal.emit(resolved_action_id, coverage)
            command = RunStaticBacktestCommand(
                symbol=self._symbol,
                interval=config.timeframe,
                strategy_key=config.strategy_key,
                initial_balance=config.initial_balance,
                start_time=config.start_time,
                end_time=config.end_time,
                strategy_params=config.strategy_params,
                cancellation_requested=(
                    cancellation_token.is_cancelled if cancellation_token else None
                ),
                progress_callback=lambda phase, completed, total, elapsed: (
                    self._backtestProgressSignal.emit(
                        resolved_action_id, phase, completed, total, elapsed
                    )
                ),
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
            self._backtestFailedSignal.emit(resolved_action_id, str(exc))
            return

        if isinstance(result, BacktestCancelled):
            self._backtestCancelledSignal.emit(resolved_action_id, result)
            return

        if result is None:
            self._log_dev_trace("worker_no_data")
            self._backtestEmptySignal.emit(
                resolved_action_id,
                f"Không có dữ liệu lịch sử cho {self._symbol} "
                f"({config.timeframe.value}). Hãy sync dữ liệu trước.",
                config,
            )
            return

        if cancellation_token is not None and cancellation_token.is_cancelled():
            self._backtestCancelledSignal.emit(
                resolved_action_id,
                BacktestCancelled("post_dispatch", 0, 0),
            )
            return

        self._log_dev_trace(
            "worker_result_ready",
            trades=len(result.trades),
            net_profit_percent=result.metrics.net_profit_percent,
        )
        self._fetch_and_emit_chart_data(resolved_action_id, config, result)
        # Emitted whether or not there are trades — _on_backtest_succeeded
        # always has a real BacktestResult to build stat cards from; only
        # "no historical data at all" (result is None, above) has none.
        self._backtestSucceededSignal.emit(resolved_action_id, result)

    def _probe_data_coverage(self, config: BacktestRunConfig) -> BacktestRangeCoverage:
        now = datetime.now(UTC)
        query = GetBacktestRangeCoverageQuery(
            symbol=self._symbol,
            interval=config.timeframe.value,
            start_time=config.start_time,
            end_time=config.end_time or now,
            now=now,
        )
        return self.dispatcher.dispatch(GetBacktestRangeCoverageQuery, query)

    def _run_sync(
        self, config: BacktestRunConfig, action_id: int | None = None
    ) -> None:
        """Background worker: dispatches `SyncMarketDataCommand` for the
        symbol/timeframe/range that just came back "no data" — mirrors
        `DataManagementPresenter._run_single_sync`, minus the progress-bar
        events that screen needs and this one doesn't (one sync, one
        outcome, no multi-target loop)."""
        resolved_action_id = action_id or self._current_action_id(
            BacktestActionKind.SYNC
        )
        if resolved_action_id is None:
            return
        self._log_dev_trace(
            "sync_worker_start",
            action_id=resolved_action_id,
            timeframe=config.timeframe.value,
            start=config.start_time,
            end=config.end_time,
        )
        try:
            command = SyncMarketDataCommand(
                symbols=[self._symbol],
                interval=config.timeframe,
                start_time=config.start_time,
                # Binance treats the history end boundary as exclusive.
                # Fetch one extra interval; coverage/backtest still keep
                # the requested half-open boundary.
                end_time=(
                    config.end_time + timedelta(seconds=config.timeframe.to_seconds())
                    if config.end_time is not None
                    else None
                ),
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
            self._syncFailedSignal.emit(resolved_action_id, str(exc))
            return
        coverage = self._probe_data_coverage(config)
        if not coverage.is_fully_covered:
            message = (
                "Đồng bộ chưa đủ để chạy Backtest: "
                f"{self._format_coverage_message(coverage)}"
            )
            self._log_dev_trace(
                "sync_coverage_incomplete",
                action_id=resolved_action_id,
                message=message,
            )
            self._syncFailedSignal.emit(resolved_action_id, message)
            return
        self._syncSucceededSignal.emit(resolved_action_id)

    def _fetch_and_emit_chart_data(
        self, action_id: int, config: BacktestRunConfig, result: BacktestResult
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
        self._chartDataReadySignal.emit(action_id, result, mapped_klines, mapped_volume)

        self._emit_strategy_indicator_lines(action_id, config, raw_klines)

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
        self, action_id: int, config: BacktestRunConfig, raw_klines: list
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
            self._chartStrategyLineSignal.emit(
                action_id, name, colors[name], x_data, y_data
            )
