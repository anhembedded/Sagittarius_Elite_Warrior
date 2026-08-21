from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QModelIndex, Signal, Slot
from PySide6.QtWidgets import QFileDialog
from Sagittarius_Elite_Warrior.src.application.events.sync_events import (
    SingleSyncProgressEvent,
)
from Sagittarius_Elite_Warrior.src.application.ports.i_symbol_market_metadata_cache import (
    ISymbolMarketMetadataCache,
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
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_realtime_backtest import (
    RunRealtimeBacktestCommand,
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
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols.query import (
    ListAvailableSymbolsQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.config.config_keys import ConfigKeys
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.trade import Trade
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.entities.symbol_market_metadata import (
    MetadataVerificationStatus,
    OrderIntent,
    validate_order_intent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_completed_event import (
    BacktestCompletedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.backtest_failed_event import (
    BacktestFailedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.events.signal_generated_event import (
    SignalGeneratedEvent,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.broker_simulation_config import (
    BrokerSimulationConfig,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizing,
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.infrastructure.persistence.symbol_market_metadata_cache import (
    InMemorySymbolMarketMetadataCache,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOwnershipTracker,
)
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
from .logic.backtest_chart_host import BacktestChartHostFactory
from .logic.backtest_event_logger import BacktestEventLogger
from .logic.backtest_fsm_matrix import (
    BACKTEST_STATE_TRANSITIONS,
    BacktestActionContext,
    BacktestActionKind,
    BacktestActionOutcome,
    BacktestExecutionMode,
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
from .logic.native_backtest_chart_host_adapter import NativeUnsupportedFeatureError
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
from .logic.strategy_trend_zones import compute_strategy_trend_zones
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
_CANCELLING_SYNC_MESSAGE = "Đang hủy đồng bộ..."
_SYNCING_MESSAGE = "Đang đồng bộ dữ liệu..."
#: BOT-111 — matches IndicatorManager.add_overlay()'s own pre-existing
#: default, so a strategy that never overrides chart_line_widths() draws
#: exactly like it did before this feature existed.
_DEFAULT_STRATEGY_LINE_WIDTH = 2
#: BOT-113 — fixed script-region key for the backtested strategy's own
#: classify_trend_zone() output. A single strategy run only ever has one
#: zone series (unlike BOT-064's reference scripts, which are keyed per
#: user-picked script), so this never needs to vary.
_STRATEGY_TREND_ZONE_KEY = "strategy_trend_zone"
_ZERO_TRADES_MESSAGE = (
    "Backtest chạy xong nhưng không có giao dịch nào trong khoảng thời gian đã chọn."
)

_EXPORT_DIALOG_TITLE = "Xuất Trade Logs"
_EXPORT_DEFAULT_FILENAME = "trade_logs.csv"
_EXPORT_FILE_FILTER = "CSV Files (*.csv)"

#: Default safety cap on chart candles, overridable via
#: ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.
#:
#: This used to be 5 000, which silently truncated the chart to the most
#: recent slice of a much longer run: a 52 000-candle backtest drew its 960
#: trade markers across the full range while only the last 5 000 candles
#: existed on the chart, so panning left ran out of candles and older markers
#: stood over empty space. Measured cost of lifting it: a 52 147-candle load
#: takes 179ms once (vs 63ms for 5 000) and pans at 18.2ms/frame — identical
#: to 5 000, because viewport windowing draws only the visible ~200 bars.
#: Range coverage itself is still checked by a compact SQLite aggregate and is
#: not inferred from this window.
_DEFAULT_CHART_KLINES_FETCH_LIMIT = 200_000

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
        int, object, list, list, list
    )  # action_id, result, klines, volume, raw_klines
    # BOT-060: line_name, color, x_data, y_data, width — one emit per line,
    # after the whole run has been fed (same O(N) reasoning as BOT-036's
    # feed_all). `width` added BOT-111 — defaults preserved via
    # BaseStrategy.chart_line_widths() returning {} for every pre-existing
    # strategy.
    _chartStrategyLineSignal = Signal(int, str, str, list, list, int)
    # BOT-113: the backtested strategy's own classify_trend_zone() output —
    # one span list per full-run replay, same action_id fencing as the
    # strategy line signal above (both fire from the same background
    # _fetch_and_emit_chart_data pass).
    _chartStrategyRegionSignal = Signal(int, list)
    # BOT-064: user-picked reference indicator scripts (RSI/MACD/...),
    # independent of the strategy's own lines above — same 4-signal shape
    # DashboardPresenter uses for IndicatorScriptRunner's 4 output channels.
    _chartScriptLineSignal = Signal(str, list, list)  # qualified name, x, y
    _chartScriptRegionSignal = Signal(str, list)  # script key, spans
    _chartScriptInfoSignal = Signal(str, list)  # script key, info fields
    _chartScriptMarkerSignal = Signal(str, list)  # script key, markers
    _syncSucceededSignal = Signal(int)  # action_id
    _syncFailedSignal = Signal(int, str)  # action_id, error message
    _syncCancelledSignal = Signal(int)  # action_id
    _syncProgressSignal = Signal(int, int, int)  # action_id, current, total
    _previewDataReadySignal = Signal(
        int, object, list, list, list
    )  # preview_id, coverage, klines, volume, raw_klines
    _uiLogSignal = Signal(str, str, bool)  # message, level, is_dev
    _symbolOptionsReadySignal = Signal(list)  # BOT-102: sorted symbol list
    _symbolOptionsFailedSignal = Signal(str)  # BOT-102: error message

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

        # BOT-102: symbol picker. `_symbol_options_cache` avoids re-hitting
        # the exchange every time the modal is reopened in the same session
        # (the tradeable symbol set does not change meaningfully within one
        # run of the app) — None means "never fetched", distinct from an
        # empty list which would mean "fetched, exchange returned nothing".
        self._symbol_options_cache: list[str] | None = None

        # BOT-059: set only by _on_backtest_empty (a real "no historical
        # data" result), cleared by any successful run or successful sync —
        # the single source of truth for whether "Đồng bộ ngay" is offered.
        self._last_no_data_config: BacktestRunConfig | None = None
        # BUG-017: the coverage probe result that produced the missing-data
        # state above, when one exists — None for the "totally empty DB, no
        # coverage was ever probed" path (_on_backtest_empty). Lets the sync
        # this triggers resume from the real gap instead of re-fetching the
        # entire originally requested range. Kept in lockstep with
        # _last_no_data_config: set/cleared at every point that field is.
        self._last_no_data_coverage: BacktestRangeCoverage | None = None

        # BOT-095B: Snapshot of the last executed backtest run configuration.
        # Used for Dirty Tracking to compare against active toolbar inputs.
        self._last_run_config: BacktestRunConfig | None = None

        # BOT-095H & EPIC-003A: shared action ownership tracker
        self._action_tracker = ActionOwnershipTracker[
            BacktestActionKind, BacktestRunConfig, BacktestUiState
        ](on_trace=self._log_dev_trace)
        self._backtest_cancellation_token: CancellationToken | None = None
        self._sync_cancellation_token: CancellationToken | None = None
        self._cancelling_action_id: int | None = None
        self._shutdown_requested = False
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
        self._current_raw_klines: list[MarketData] = []
        self._chart_klines_fetch_limit = int(
            self.config.get(
                ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value,
                _DEFAULT_CHART_KLINES_FETCH_LIMIT,
            )
            or _DEFAULT_CHART_KLINES_FETCH_LIMIT
        )
        try:
            resolved_cache = container.resolve(ISymbolMarketMetadataCache)
            self._market_metadata_cache: ISymbolMarketMetadataCache = (
                resolved_cache
                if isinstance(resolved_cache, ISymbolMarketMetadataCache)
                else InMemorySymbolMarketMetadataCache()
            )
        except Exception:  # noqa: BLE001
            self._market_metadata_cache = InMemorySymbolMarketMetadataCache()

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
        # BOT-102: mirrors the config-derived self._symbol so the picker
        # highlights the right entry even before it's ever been opened.
        self._view_model.selectedSymbol = self._symbol
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
        self._refresh_market_rule_verification()

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
        # BUG-009: defaults to OFF. The cached-frame preview replaces live
        # rendering with a translated snapshot of the last frame, and every
        # symptom the user reported follows from that one decision — the
        # snapshot holds no pixels past its own edge (blank band), its Y axis
        # cannot re-autoscale (vertical jump on release), and its indicator
        # and volume windows are frozen at capture time. None of that is
        # fixable while the frame is a snapshot.
        #
        # Its premise no longer holds either: CHART_CARD_MAX_ZOOM_OUT_CANDLES
        # caps the plot at ~200 visible candles, so a real pan re-render costs
        # ~32ms regardless of how much history is loaded — bounded, not
        # unbounded. Dragging from the volume subplot already bypasses the
        # preview and pans natively, and that path was confirmed defect-free
        # in use. Set this key to true to opt back in.
        view.set_chart_cached_interaction_enabled(
            bool(
                self.config.get(
                    ConfigKeys.BACKTEST_CHART_CACHED_INTERACTION_ENABLED.value,
                    False,
                )
            )
        )
        # BOT-098F6E: Default backend is now "auto" (attempts native first,
        # falls back to python). "python" remains as explicit fallback override.
        view.set_chart_host_factory(self.container.resolve(BacktestChartHostFactory))
        view.set_chart_backend(
            str(self.config.get(ConfigKeys.BACKTEST_CHART_BACKEND.value, "auto"))
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
        self._view_model.selectedSymbolChanged.connect(
            self._on_symbol_selection_changed
        )
        self._view_model.openSymbolPickerRequested.connect(
            self._on_symbol_picker_open_requested
        )
        self._view_model.executionModeChanged.connect(self._on_execution_mode_changed)
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
        self._view_model.strategyPropertiesSaveRequested.connect(
            self._on_strategy_properties_save_requested
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
        self._chartStrategyRegionSignal.connect(
            self._on_chart_strategy_region_for_action
        )
        self._chartScriptLineSignal.connect(self._on_chart_script_line)
        self._chartScriptRegionSignal.connect(self._on_chart_script_region)
        self._chartScriptInfoSignal.connect(self._on_chart_script_info)
        self._chartScriptMarkerSignal.connect(self._on_chart_script_marker)
        self._syncSucceededSignal.connect(self._on_sync_succeeded_for_action)
        self._syncFailedSignal.connect(self._on_sync_failed_for_action)
        self._syncCancelledSignal.connect(self._on_sync_cancelled_for_action)
        self._syncProgressSignal.connect(self._on_sync_progress_for_action)
        self._previewDataReadySignal.connect(self._on_preview_data_ready)
        self._uiLogSignal.connect(self._on_ui_log)
        self._symbolOptionsReadySignal.connect(self._on_symbol_options_ready)
        self._symbolOptionsFailedSignal.connect(self._on_symbol_options_failed)
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

        chart_cards = self.view.chart_cards
        if chart_cards:
            chart_cards[0].connect_timeframe_changed(
                self._on_chart_toolbar_timeframe_selected
            )
            self._sync_chart_toolbar_timeframe()

    @Slot(str)
    @safe_ui_action
    def _on_chart_toolbar_timeframe_selected(self, timeframe: str) -> None:
        """Make a chart-header timeframe click change the Backtest data contract."""
        if timeframe != self._view_model.selectedTimeframe:
            self._view_model.selectedTimeframe = timeframe

    def _sync_chart_toolbar_timeframe(self) -> None:
        """Mirror the ViewModel timeframe in the visible native chart header."""
        if self.view.chart_cards:
            self.view.chart_cards[0].set_active_timeframe(
                self._view_model.selectedTimeframe
            )

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

    @property
    def _active_action(self) -> BacktestActionContext | None:
        return self._action_tracker.active_action

    @property
    def _active_action_outcome(self) -> BacktestActionOutcome | None:
        return self._action_tracker.active_outcome

    def _begin_action(
        self,
        kind: BacktestActionKind,
        config: BacktestRunConfig,
        previous_state: BacktestUiState,
    ) -> BacktestActionContext:
        """Create the immutable owner record before background submission."""
        return self._action_tracker.begin_action(kind, config, previous_state)

    def _is_current_action(self, action_id: int, kind: BacktestActionKind) -> bool:
        return self._action_tracker.is_current(action_id, kind)

    def _is_current_pending_action(
        self, action_id: int, kind: BacktestActionKind
    ) -> bool:
        return self._action_tracker.is_current_pending(action_id, kind)

    def _current_action_id(self, kind: BacktestActionKind) -> int | None:
        return self._action_tracker.current_action_id(kind)

    def _finish_action(self, action_id: int, outcome: BacktestActionOutcome) -> None:
        self._action_tracker.finish_action(action_id, outcome)

    def _invalidate_active_action(self) -> None:
        """Invalidate a pending action without assigning a replacement.

        BOT-095C's cancel flow will call this before requesting cooperative
        worker cancellation, so late callbacks are fenced immediately.
        """
        self._action_tracker.invalidate_active()

    def _ignore_stale_action_callback(
        self, callback: str, action_id: int, kind: BacktestActionKind
    ) -> None:
        self._action_tracker.log_stale_callback(callback, action_id, kind)

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
            execution_mode=self._get_execution_mode_from_view_model(),
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
            card.clear_script_regions(_STRATEGY_TREND_ZONE_KEY)
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
        self._last_no_data_coverage = coverage
        self._view_model.set_data_coverage(False, message)
        self._view_model.set_needs_data_sync(True)
        self._finish_action(action_id, BacktestActionOutcome.EMPTY)
        if allow_auto_sync:
            if self.fsm.can_dispatch(BacktestUiEvent.BACKTEST_EMPTY):
                self.fsm.dispatch(BacktestUiEvent.BACKTEST_EMPTY)
            self._start_sync_for_config(config, coverage)
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
        """Cancels whichever action is currently active — a Backtest run
        (RUNNING) or a data sync (SYNCING); the two states are mutually
        exclusive by FSM construction, so `self._active_action.kind` alone
        disambiguates which token to cancel. Kept as one shared handler
        rather than a parallel `_on_cancel_sync` because every other piece
        of the cancel lifecycle (`_is_cancelling_action`,
        `_complete_cancelled_action`, the CANCELLING resolution transitions)
        was already kind-agnostic except for this entry point."""
        if self._active_action is None:
            self._log_dev_trace("cancel_ignored", state=self.fsm.current_state)
            return
        action_id = self._active_action.action_id
        kind = self._active_action.kind
        if not self._is_current_pending_action(
            action_id, kind
        ) or not self.fsm.can_dispatch(BacktestUiEvent.CANCEL_REQUESTED):
            self._log_dev_trace("cancel_ignored", state=self.fsm.current_state)
            return

        self._cancelling_action_id = action_id
        self._invalidate_active_action()
        self.fsm.dispatch(BacktestUiEvent.CANCEL_REQUESTED)
        if kind is BacktestActionKind.SYNC:
            if self._sync_cancellation_token is not None:
                self._sync_cancellation_token.cancel()
            self._view_model.set_result(_CANCELLING_SYNC_MESSAGE, is_error=False)
            self._emit_ui_log("Đang gửi yêu cầu hủy đồng bộ...", "info")
        else:
            if self._backtest_cancellation_token is not None:
                self._backtest_cancellation_token.cancel()
            self._view_model.set_result(_CANCELLING_MESSAGE, is_error=False)
            self._emit_ui_log("Đang gửi yêu cầu hủy Backtest...", "info")
        self._log_dev_trace("cancel_requested", action_id=action_id, kind=kind.value)
        self._log_dev_trace("cancel_requested", action_id=action_id)

    def _is_cancelling_action(self, action_id: int) -> bool:
        """Kind-agnostic on purpose: `self._active_action` is a single slot
        regardless of whether it holds a Backtest run or a Sync (BOT-095B's
        own design — see `_begin_action`), so `action_id` alone already
        disambiguates which one without also checking `kind` here."""
        return (
            self._active_action is not None
            and self._active_action.action_id == action_id
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
        kind = self._active_action.kind
        previous_state = self._active_action.previous_state
        self._finish_action(action_id, BacktestActionOutcome.CANCELLED)
        self._cancelling_action_id = None
        if kind is BacktestActionKind.SYNC:
            self._sync_cancellation_token = None
            self._view_model.reset_sync_progress()
            message = "Đã hủy đồng bộ dữ liệu."
        else:
            self._backtest_cancellation_token = None
            self._view_model.reset_backtest_progress()
            message = "Đã hủy Backtest. Kết quả trước đó được giữ nguyên."
        self._view_model.set_result(message, is_error=False)
        self._emit_ui_log(message, "info")
        event = self._cancel_restore_event(previous_state)
        if self.fsm.can_dispatch(event):
            self.fsm.dispatch(event)
        self._log_dev_trace(
            "cancel_completed",
            action_id=action_id,
            kind=kind.value,
            restore_state=previous_state.value,
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

    @Slot(int, object, list, list, list)
    @safe_ui_action
    def _on_chart_data_ready_for_action(
        self,
        action_id: int,
        result: BacktestResult,
        klines: list,
        volume: list,
        raw_klines: list,
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "chart_data_ready", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_chart_data_ready(result, klines, volume, raw_klines)

    @Slot(int, str, str, list, list, int)
    @safe_ui_action
    def _on_chart_strategy_line_for_action(
        self,
        action_id: int,
        name: str,
        color: str,
        x_data: list,
        y_data: list,
        width: int,
    ) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "chart_strategy_line", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_chart_strategy_line(name, color, x_data, y_data, width)

    @Slot(int, list)
    @safe_ui_action
    def _on_chart_strategy_region_for_action(self, action_id: int, spans: list) -> None:
        if not self._is_current_pending_action(action_id, BacktestActionKind.BACKTEST):
            self._ignore_stale_action_callback(
                "chart_strategy_region", action_id, BacktestActionKind.BACKTEST
            )
            return
        self._on_chart_strategy_region(spans)

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
        self._last_no_data_coverage = None
        self._view_model.set_needs_data_sync(False)
        self._view_model.set_stat_cards(
            stat_cards_to_qml(build_primary_stat_cards(result)),
            stat_cards_to_qml(build_extended_stat_cards(result)),
        )
        self._view_model.set_result_warning_text(build_result_warning_text(result))
        self._view_model.set_limitations(build_backtest_limitations(result))
        run_config = self._get_current_config()
        message = (
            format_result_summary(result)
            if result.trades
            else f"{_ZERO_TRADES_MESSAGE}\n\n{format_result_summary(result)}"
        )
        message = f"{self._execution_mode_label(run_config)}\n{message}"
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
        self._last_run_config = run_config
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
        # No coverage probe backs this path (totally empty DB) — must not
        # reuse a stale gap from an earlier, unrelated missing-coverage
        # event, or the next sync would resume from the wrong point.
        self._last_no_data_coverage = None
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

    @Slot(object, list, list, list)
    @safe_ui_action
    def _on_chart_data_ready(
        self,
        result: BacktestResult,
        klines: list,
        volume: list,
        raw_klines: list | None = None,
    ) -> None:
        if raw_klines is not None:
            self._current_raw_klines = list(raw_klines)
            self._refresh_market_rule_verification()
        self._log_dev_trace(
            "chart_data_ready",
            klines=len(klines),
            volume=len(volume),
            trades=len(result.trades),
        )
        self._logger.log_klines_loaded(len(klines), self._symbol)
        try:
            self.view.on_backtest_data_ready(result, klines, volume)
        except NativeUnsupportedFeatureError:
            self._fallback_to_python_after_unsupported_native_feature(
                "backtest OHLCV data"
            )

    @Slot(str, str, list, list)
    @safe_ui_action
    def _on_chart_strategy_line(
        self, name: str, color: str, x_data: list, y_data: list, width: int = 2
    ) -> None:
        """BOT-060: one call per strategy indicator line, emitted once the
        whole run has been fed (`_fetch_and_emit_chart_data`) — adds the
        curve on first use, same as `IndicatorScriptRunner.draw()` does for
        Dev Board scripts, just without needing that class at all (a
        strategy has no `.line_colors()`/`.compute()` to drive it). `width`
        (BOT-111) lets a strategy request a different line weight per line,
        e.g. a thinner entry EMA than trend EMA — Python `ChartCard` only;
        the native chart's indicator ABI has no per-line width concept."""
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is None:
            return
        if name not in self._active_strategy_lines:
            card.add_overlay_indicator(name, color, width)
            self._active_strategy_lines.add(name)
        card.update_indicator_data(name, x_data, y_data)

    @Slot(list)
    @safe_ui_action
    def _on_chart_strategy_region(self, spans: list) -> None:
        """BOT-113: the backtested strategy's own `classify_trend_zone()`
        output, emitted once per run (`_emit_strategy_trend_zones`) under a
        fixed key — unlike `_on_chart_script_region` there is only ever one
        strategy per run, so no key needs to travel through the signal.
        Native chart has no background-region ABI at all (BOT-032's own
        scope boundary); same fallback-to-Python path every other
        native-unsupported feature already uses."""
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is None:
            return
        try:
            card.set_script_regions(_STRATEGY_TREND_ZONE_KEY, spans)
        except NativeUnsupportedFeatureError:
            self._fallback_to_python_after_unsupported_native_feature(
                "strategy trend zones"
            )

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
        if card is None:
            return
        try:
            self._chart_script_runner.draw_region(card, key, spans)
        except NativeUnsupportedFeatureError:
            self._fallback_to_python_after_unsupported_native_feature("script regions")

    @Slot(str, list)
    @safe_ui_action
    def _on_chart_script_info(self, key: str, fields: list) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is None:
            return
        try:
            self._chart_script_runner.draw_info(card, key, fields)
        except NativeUnsupportedFeatureError:
            self._fallback_to_python_after_unsupported_native_feature("script info")

    @Slot(str, list)
    @safe_ui_action
    def _on_chart_script_marker(self, key: str, markers: list) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is None:
            return
        try:
            self._chart_script_runner.draw_markers(card, key, markers)
        except NativeUnsupportedFeatureError:
            self._fallback_to_python_after_unsupported_native_feature("script markers")

    def _reset_indicator_bookkeeping_after_host_rebuild(self) -> None:
        """The chart host was just replaced from scratch — nothing on the
        new one knows about strategy/script indicator lines drawn on the
        old one, and neither caches the underlying x/y series to replay, so
        drop the stale bookkeeping rather than let it silently desync
        (BOT-098F6D bug, 2026-08-18: real run-ui.ps1 session — indicator
        lines vanished after a chart-mode round-trip, then the next
        set_indicator_visible() call crashed and was swallowed silently by
        safe_ui_action). Re-running the backtest already redraws every line
        from scratch, same as before host rebuilding existed.

        Shared by every rebuild path — `_on_chart_mode_changed()` and
        `_fallback_to_python_after_unsupported_native_feature()` — because
        skipping it is not just a cosmetic gap: `IndicatorScriptRunner`'s
        `ResourceScope` still holds a dispose callback bound to the
        already-`deleteLater()`'d old host, and the *next* backtest run's
        `clear_from_chart()` invokes it unconditionally, crashing with a
        real shiboken "C++ object already deleted" `RuntimeError`
        (BUG-013, 2026-08-19 — found reachable only through the fallback
        path, since F6D's own fix here only covered the mode-change path)."""
        self._active_strategy_lines.clear()
        self._chart_script_runner.reset_after_host_replaced()

    def _fallback_to_python_after_unsupported_native_feature(
        self, feature_name: str
    ) -> None:
        """BOT-098F6D: content outside native's OHLC/volume/indicator/
        truthful-marker scope (script regions/info/arbitrary markers,
        equity/BOTH subplot) must never be silently dropped — rebuild with
        the Python host so it actually renders, and log exactly once why."""
        self._log_dev_trace(
            "native_chart_unsupported_feature_fallback", feature=feature_name
        )
        logger.warning(
            "Native Backtest chart does not support %s; rebuilding with the "
            "Python host.",
            feature_name,
        )
        self.view.set_chart_backend("python")
        self.view.render_symbol_cards([self._symbol])
        self._reset_indicator_bookkeeping_after_host_rebuild()
        self._connect_chart_controls()
        self.view.refresh_chart()

    @Slot(str)
    @safe_ui_action
    def _on_chart_mode_changed(self, mode_value: str) -> None:
        mode = ChartDisplayMode(mode_value)
        self._log_dev_trace("chart_mode_changed", mode=mode_value)
        rebuilt = self.view.set_chart_mode(mode)
        if rebuilt:
            self._reset_indicator_bookkeeping_after_host_rebuild()
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
    def _on_symbol_picker_open_requested(self) -> None:
        """BOT-102: fetches the tradeable symbol list from the exchange the
        first time the picker is opened in this session; a cache hit means
        the modal already has `symbolOptions` populated from a prior open
        and this is a no-op."""
        if self._symbol_options_cache is not None:
            return
        self._thread_manager.submit(self._fetch_symbol_options)

    def _fetch_symbol_options(self) -> None:
        try:
            symbols = self.dispatcher.dispatch(
                ListAvailableSymbolsQuery, ListAvailableSymbolsQuery()
            )
        except Exception as exc:
            logger.exception("Failed to fetch available symbols")
            self._symbolOptionsFailedSignal.emit(str(exc))
            return
        self._symbolOptionsReadySignal.emit(symbols)

    @Slot(list)
    def _on_symbol_options_ready(self, symbols: list[str]) -> None:
        self._symbol_options_cache = symbols
        self._view_model.set_symbol_options(symbols)

    @Slot(str)
    def _on_symbol_options_failed(self, message: str) -> None:
        self._emit_ui_log(
            f"Không tải được danh sách symbol từ sàn: {message}", level="error"
        )

    @Slot()
    @safe_ui_action
    def _on_symbol_selection_changed(self) -> None:
        """BOT-102: the picker only ever writes valid, already-picked values
        to `selectedSymbol` — this mirrors that choice into `self._symbol`,
        the plain attribute every command/query dispatch actually reads
        (kept separate from the ViewModel property because background
        workers must never touch the ViewModel directly)."""
        new_symbol = self._view_model.selectedSymbol
        if not new_symbol or new_symbol == self._symbol:
            return
        self._symbol = new_symbol
        # Full chart host rebuild, same as every other render_symbol_cards()
        # call site outside __init__ (BOT-098F6D's native-fallback path) —
        # skipping the bookkeeping reset/reconnect leaves the new host's
        # controls unwired and stale ResourceScope dispose callbacks bound
        # to the just-deleted old host (BUG-013). Deliberately NOT calling
        # view.refresh_chart() here: it replays _last_klines/_last_result,
        # which still belong to the PREVIOUS symbol — _request_chart_preview()
        # below fetches and renders fresh data for the new one instead.
        self.view.render_symbol_cards([self._symbol])
        self._reset_indicator_bookkeeping_after_host_rebuild()
        self._connect_chart_controls()
        self._emit_ui_log(f"Đã đổi symbol sang {self._symbol}.")
        self._on_config_input_changed()
        self._request_chart_preview()

    @Slot()
    @safe_ui_action
    def _on_timeframe_changed(self) -> None:
        self._logger.log_timeframe_selected(self._view_model.selectedTimeframe)
        self._sync_chart_toolbar_timeframe()
        self._on_config_input_changed()
        self._request_chart_preview()

    @Slot()
    @safe_ui_action
    def _on_execution_mode_changed(self) -> None:
        """BOT-076 §3.3 — OrderExecutionModal's mode selection changed."""
        logger.info(
            "[backtest-config] execution mode set to %s",
            self._view_model.executionMode,
        )
        self._on_config_input_changed()

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
                limit=self._chart_klines_fetch_limit,
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
                raw_klines,
            )
        except Exception as exc:
            logger.exception("Fetching Backtest chart preview failed")
            self._log_dev_trace("preview_query_failed", message=str(exc))

    @Slot(int, object, list, list, list)
    @safe_ui_action
    def _on_preview_data_ready(
        self,
        preview_id: int,
        coverage: BacktestRangeCoverage,
        klines: list,
        volume: list,
        raw_klines: list | None = None,
    ) -> None:
        if preview_id != self._active_preview_id:
            self._log_dev_trace("preview_ignored", preview_id=preview_id)
            return
        if raw_klines is not None:
            self._current_raw_klines = list(raw_klines)
        self._view_model.set_data_coverage(
            coverage.is_fully_covered,
            ""
            if coverage.is_fully_covered
            else self._format_coverage_message(coverage),
        )
        self._view_model.set_needs_data_sync(not coverage.is_fully_covered)
        try:
            self.view.on_preview_data_ready(klines, volume)
        except NativeUnsupportedFeatureError:
            self._fallback_to_python_after_unsupported_native_feature(
                "chart preview data"
            )

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
        self._refresh_market_rule_verification()

    def _refresh_market_rule_verification(self) -> None:
        """Evaluates whether current symbol and capital comply with exchange order rules (BOT-095E1)."""
        metadata = self._market_metadata_cache.get(self._symbol)
        try:
            capital_val = float(self._view_model.initialCapitalText)
        except (ValueError, TypeError):
            capital_val = 0.0

        if metadata is None:
            self._view_model.set_market_rule_verification(
                MetadataVerificationStatus.UNVERIFIED_MISSING.value,
                "Chưa xác minh theo quy tắc sàn (chưa có metadata cho cặp giao dịch).",
            )
            return

        if metadata.is_stale():
            self._view_model.set_market_rule_verification(
                MetadataVerificationStatus.UNVERIFIED_STALE.value,
                f"Chưa xác minh theo quy tắc sàn (metadata cũ từ {metadata.fetched_at.strftime('%Y-%m-%d %H:%M:%S UTC')}).",
            )
            return

        ref_price = (
            self._current_raw_klines[-1].close_price
            if self._current_raw_klines
            else metadata.price_filter.min_price
        )
        qty = capital_val / ref_price if ref_price > 0 else 0.0
        intent = OrderIntent(symbol=self._symbol, price=ref_price, quantity=qty)
        result = validate_order_intent(intent, metadata)
        self._view_model.set_market_rule_verification(
            result.status.value,
            result.explanation,
        )

    @Slot()
    @safe_ui_action
    def _on_indicator_script_selection_changed(self) -> None:
        """BOT-095F: dynamically adds or removes reference indicator scripts from the chart
        when toggled in the indicator picker modal, without requiring a full backtest rerun."""
        enabled_keys = set(self._view_model.script_model.enabled_keys)
        scripts_str = ", ".join(sorted(enabled_keys)) if enabled_keys else "Không có"
        self._logger.info(f"Đã cập nhật chỉ báo tham chiếu: {scripts_str}")

        current_active_keys = set(self._chart_script_runner.active.keys())
        disabled_keys = current_active_keys - enabled_keys
        newly_enabled_keys = enabled_keys - current_active_keys

        card = self.view.chart_cards[0] if self.view.chart_cards else None

        for key in disabled_keys:
            if card is not None:
                self._chart_script_runner.remove_script(key, card)
            else:
                self._chart_script_runner.active.pop(key, None)

        if self._current_raw_klines:
            is_price_scale = (
                getattr(self.view, "chart_mode", ChartDisplayMode.OHLC)
                is not ChartDisplayMode.EQUITY
            )
            for key in newly_enabled_keys:
                self._chart_script_runner.add_script(key, self._current_raw_klines)
                if not is_price_scale:
                    active = self._chart_script_runner.active.get(key)
                    if active and active.overlay and card is not None:
                        for line_name in active.registered_lines:
                            card.set_indicator_visible(
                                qualified_line_name(key, line_name), False
                            )

        self._chart_script_keys = sorted(enabled_keys)

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

    @Slot(object)
    @safe_ui_action
    def _on_strategy_properties_save_requested(self, payload: dict) -> None:
        """ "Lưu & Chạy lại" (BOT-104): handles combined Strategy Inputs and
        Broker Properties saving from StrategyPropertiesModal.qml."""
        inputs = payload.get("inputs", {})
        props = payload.get("properties", {})

        strategy_cls = self._strategy_registry.available().get(
            self._view_model.selectedStrategyKey
        )
        if strategy_cls is not None and inputs:
            try:
                parsed = parse_bot_params(strategy_cls().inputs, inputs)
                strategy_cls(parsed)
                self._strategy_params = parsed
            except ValueError as exc:
                self._view_model.set_bot_params_error(str(exc))
                return

        # Apply broker properties to view_model
        if "initial_capital" in props:
            self._view_model.initialCapitalText = str(props["initial_capital"])
        if "currency" in props:
            self._view_model.selectedCurrency = str(props["currency"])
        if "order_size_type" in props:
            self._view_model.orderSizeType = str(props["order_size_type"])
        if "order_size_text" in props:
            self._view_model.orderSizeText = str(props["order_size_text"])
        if "pyramiding" in props:
            self._view_model.pyramiding = int(props["pyramiding"])
        if "commission_type" in props:
            self._view_model.commissionType = str(props["commission_type"])
        if "commission_text" in props:
            self._view_model.commissionText = str(props["commission_text"])
        if "slippage_ticks" in props:
            self._view_model.slippageTicks = int(props["slippage_ticks"])
        if "long_leverage" in props:
            self._view_model.longLeverage = float(props["long_leverage"])
        if "short_leverage" in props:
            self._view_model.shortLeverage = float(props["short_leverage"])
        if "take_profit_enabled" in props:
            self._view_model.takeProfitPctEnabled = bool(props["take_profit_enabled"])
        if "take_profit_pct_text" in props:
            self._view_model.takeProfitPctText = str(props["take_profit_pct_text"])

        self._view_model.set_bot_params_error("")
        self._refresh_bot_params_schema()
        self._view_model.botParamsSaved.emit()
        self._logger.log_bot_params_saved(
            self._view_model.selectedStrategyName,
            self._strategy_params or {},
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
        self._start_sync_for_config(
            self._last_no_data_config, self._last_no_data_coverage
        )

    def _start_sync_for_config(
        self,
        sync_config: BacktestRunConfig,
        coverage: BacktestRangeCoverage | None = None,
    ) -> None:
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
        self._sync_cancellation_token = CancellationToken()
        self._thread_manager.submit(
            self._run_sync,
            action.config,
            action.action_id,
            self._sync_cancellation_token,
            coverage,
        )

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
        # A cancel can race a sync that was already past its last
        # cooperative check — the worker then finishes and reports success
        # normally instead of taking the _syncCancelledSignal path. Without
        # this, that race would leave the FSM stuck in CANCELLING forever,
        # since only _complete_cancelled_action ever resolves it out.
        if self._is_cancelling_action(action_id):
            self._complete_cancelled_action(action_id)
            return
        if not self._is_current_pending_action(action_id, BacktestActionKind.SYNC):
            self._ignore_stale_action_callback(
                "sync_succeeded", action_id, BacktestActionKind.SYNC
            )
            return
        self._sync_cancellation_token = None
        self._finish_action(action_id, BacktestActionOutcome.SUCCEEDED)
        self._on_sync_succeeded()

    @Slot(int, str)
    @safe_ui_action
    def _on_sync_failed_for_action(self, action_id: int, message: str) -> None:
        if self._is_cancelling_action(action_id):
            self._complete_cancelled_action(action_id)
            return
        if not self._is_current_pending_action(action_id, BacktestActionKind.SYNC):
            self._ignore_stale_action_callback(
                "sync_failed", action_id, BacktestActionKind.SYNC
            )
            return
        self._sync_cancellation_token = None
        self._on_sync_failed(message)
        self._finish_action(action_id, BacktestActionOutcome.FAILED)

    @Slot(int)
    @safe_ui_action
    def _on_sync_cancelled_for_action(self, action_id: int) -> None:
        if not self._is_cancelling_action(action_id):
            self._ignore_stale_action_callback(
                "sync_cancelled", action_id, BacktestActionKind.SYNC
            )
            return
        self._log_dev_trace("worker_cancelled", action_id=action_id, kind="SYNC")
        self._complete_cancelled_action(action_id)

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
        self._last_no_data_coverage = None
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
                is_unbounded_range=preset is TimeRangePreset.ALL_HISTORY,
                is_tick_mode=self._get_execution_mode_from_view_model()
                is BacktestExecutionMode.HISTORICAL_TICK,
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

        try:
            order_sizing_type = PositionSizingType(view_model.orderSizeType)
        except ValueError:
            order_sizing_type = PositionSizingType.PERCENT_OF_EQUITY

        position_sizing = PositionSizing(
            type=order_sizing_type,
            value=view_model.orderSizeValue,
        )

        try:
            commission_type = CommissionType(view_model.commissionType)
        except ValueError:
            commission_type = CommissionType.PERCENT

        take_profit_pct: float | None = None
        if view_model.takeProfitPctEnabled:
            try:
                parsed_take_profit_pct = float(view_model.takeProfitPctText)
            except ValueError:
                parsed_take_profit_pct = 0.0
            if parsed_take_profit_pct > 0:
                take_profit_pct = parsed_take_profit_pct

        broker_config = BrokerSimulationConfig(
            pyramiding=view_model.pyramiding,
            slippage_ticks=view_model.slippageTicks,
            commission_type=commission_type,
            commission_value=view_model.commissionValue,
            long_leverage=view_model.longLeverage,
            short_leverage=view_model.shortLeverage,
            take_profit_pct=take_profit_pct,
        )

        return BacktestRunConfig(
            strategy_key=view_model.selectedStrategyKey,
            timeframe=TimeFrame(view_model.selectedTimeframe),
            initial_balance=initial_balance,
            start_time=start_time,
            end_time=end_time,
            strategy_params=self._strategy_params,
            currency=Currency(view_model.selectedCurrency),
            symbol=self._symbol,
            execution_mode=self._get_execution_mode_from_view_model(),
            position_sizing=position_sizing,
            broker_config=broker_config,
        )

    def _get_execution_mode_from_view_model(self) -> BacktestExecutionMode:
        try:
            return BacktestExecutionMode(self._view_model.executionMode)
        except ValueError:
            return BacktestExecutionMode.BAR_CLOSE

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

            def progress_callback(
                phase: str, completed: int, total: int, elapsed: float
            ) -> None:
                self._backtestProgressSignal.emit(
                    resolved_action_id, phase, completed, total, elapsed
                )

            cancellation_requested = (
                cancellation_token.is_cancelled if cancellation_token else None
            )
            if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK:
                realtime_command = RunRealtimeBacktestCommand(
                    symbol=self._symbol,
                    interval=config.timeframe,
                    tick_resolution=config.tick_resolution,
                    strategy_key=config.strategy_key,
                    initial_balance=config.initial_balance,
                    fee_percent=config.broker_config.commission_value
                    if config.broker_config.commission_type == CommissionType.PERCENT
                    else 0.0,
                    position_sizing=config.position_sizing,
                    broker_config=config.broker_config,
                    start_time=config.start_time,
                    end_time=config.end_time,
                    strategy_params=config.strategy_params,
                    cancellation_requested=cancellation_requested,
                    progress_callback=progress_callback,
                )
                self._log_dev_trace(
                    "worker_dispatch_run_realtime_backtest",
                    symbol=realtime_command.symbol,
                    timeframe=realtime_command.interval.value,
                    tick_resolution=realtime_command.tick_resolution.value,
                )
                result = self.dispatcher.dispatch(
                    RunRealtimeBacktestCommand, realtime_command
                )
            else:
                static_command = RunStaticBacktestCommand(
                    symbol=self._symbol,
                    interval=config.timeframe,
                    strategy_key=config.strategy_key,
                    initial_balance=config.initial_balance,
                    fee_percent=config.broker_config.commission_value
                    if config.broker_config.commission_type == CommissionType.PERCENT
                    else 0.0,
                    position_sizing=config.position_sizing,
                    broker_config=config.broker_config,
                    start_time=config.start_time,
                    end_time=config.end_time,
                    strategy_params=config.strategy_params,
                    cancellation_requested=cancellation_requested,
                    progress_callback=progress_callback,
                )
                self._log_dev_trace(
                    "worker_dispatch_run_static_backtest",
                    symbol=static_command.symbol,
                    timeframe=static_command.interval.value,
                )
                result = self.dispatcher.dispatch(
                    RunStaticBacktestCommand, static_command
                )
        except Exception as exc:
            logger.exception(
                "%s backtest failed",
                "Realtime"
                if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK
                else "Static",
            )
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
                f"({self._effective_data_interval(config).value}). "
                "Hãy sync dữ liệu trước.",
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

    @staticmethod
    def _execution_mode_label(config: BacktestRunConfig) -> str:
        """BOT-076 §3.3 — every result must say plainly which of the two
        parallel engines produced it. They are allowed and expected to
        disagree on the same data (BOT-076 §5); a result with no label is
        exactly the "two runs look identical with different meanings" trap
        that requirement exists to prevent."""
        if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK:
            return f"Chế độ: Realtime (tick {config.tick_resolution.value})"
        return "Chế độ: Static (theo nến đóng)"

    @staticmethod
    def _effective_data_interval(config: BacktestRunConfig) -> TimeFrame:
        """The kline interval that must actually be synced/covered for this
        run — BOT-076's realtime handler queries `IMarketDataRepository` at
        `tick_resolution` (e.g. 1s), never at `config.timeframe` (the
        strategy/indicator interval, e.g. 5m — BOT-075's own decision was 1s
        kline as the tick data source, same repository, no new pipeline).
        Checking/syncing `config.timeframe` coverage for a Realtime run would
        report "fully covered" while the interval the handler actually reads
        was never fetched at all."""
        if config.execution_mode == BacktestExecutionMode.HISTORICAL_TICK:
            return config.tick_resolution
        return config.timeframe

    def _probe_data_coverage(self, config: BacktestRunConfig) -> BacktestRangeCoverage:
        now = datetime.now(UTC)
        query = GetBacktestRangeCoverageQuery(
            symbol=self._symbol,
            interval=self._effective_data_interval(config).value,
            start_time=config.start_time,
            end_time=config.end_time or now,
            now=now,
        )
        return self.dispatcher.dispatch(GetBacktestRangeCoverageQuery, query)

    @staticmethod
    def _resolve_sync_start(
        config: BacktestRunConfig, coverage: BacktestRangeCoverage | None
    ) -> datetime | None:
        """BUG-017: resume a sync from the coverage-detected gap instead of
        re-fetching the entire originally requested range, when a prior
        coverage probe found one. `coverage` is only ever `None` for the
        "totally empty DB, nothing was ever probed" path — the full
        requested range genuinely is missing there, so falling back to
        `config.start_time` is correct, not the bug this guards against.
        Always logged (not gated on --dev): explains after the fact why a
        given sync fetched however many candles it did."""
        if coverage is not None and coverage.missing_open_times:
            gap_start = coverage.missing_open_times[0]
            logger.info(
                f"{_TRACE_PREFIX} action=sync_start_resolved source=coverage_gap "
                f"gap_start={gap_start!r} requested_start={config.start_time!r}"
            )
            return gap_start
        logger.info(
            f"{_TRACE_PREFIX} action=sync_start_resolved source=requested_range "
            f"requested_start={config.start_time!r}"
        )
        return config.start_time

    def _run_sync(
        self,
        config: BacktestRunConfig,
        action_id: int | None = None,
        cancellation_token: CancellationToken | None = None,
        coverage: BacktestRangeCoverage | None = None,
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
        sync_interval = self._effective_data_interval(config)
        sync_start = self._resolve_sync_start(config, coverage)
        self._log_dev_trace(
            "sync_worker_start",
            action_id=resolved_action_id,
            timeframe=sync_interval.value,
            start=sync_start,
            end=config.end_time,
        )
        try:
            command = SyncMarketDataCommand(
                symbols=[self._symbol],
                interval=sync_interval,
                start_time=sync_start,
                # Binance treats the history end boundary as exclusive.
                # Fetch one extra interval; coverage/backtest still keep
                # the requested half-open boundary.
                end_time=(
                    config.end_time + timedelta(seconds=sync_interval.to_seconds())
                    if config.end_time is not None
                    else None
                ),
                cancellation_requested=(
                    cancellation_token.is_cancelled if cancellation_token else None
                ),
            )
            self._log_dev_trace(
                "sync_dispatch",
                symbol=self._symbol,
                timeframe=sync_interval.value,
            )
            self.dispatcher.dispatch(SyncMarketDataCommand, command)
        except Exception as exc:
            logger.exception("Market data sync failed")
            self._log_dev_trace("sync_worker_failed", message=str(exc))
            self._syncFailedSignal.emit(resolved_action_id, str(exc))
            return
        if cancellation_token is not None and cancellation_token.is_cancelled():
            self._log_dev_trace("sync_worker_cancelled", action_id=resolved_action_id)
            # Whatever candles landed before cancellation stay in the DB —
            # SyncMarketDataCommandHandler checks the token cooperatively and
            # returns normally rather than raising, so this is the only place
            # a cancelled sync is distinguishable from one that quietly ran
            # to completion. Previously this just returned here with no
            # signal at all, leaving the FSM stuck in SYNCING forever with no
            # way out once cancel was requested.
            self._syncCancelledSignal.emit(resolved_action_id)
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

    def shutdown(self) -> None:
        """Cancels owned workers before the desktop UI and engine are torn down."""
        if self._shutdown_requested:
            return
        self._shutdown_requested = True
        self._invalidate_active_action()
        self._active_preview_id += 1
        if self._backtest_cancellation_token is not None:
            self._backtest_cancellation_token.cancel()
        if self._sync_cancellation_token is not None:
            self._sync_cancellation_token.cancel()

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
        if result.committed_bars:
            # A Realtime run built its own bars by aggregating ticks, so the
            # exchange's published candles for this interval are a DIFFERENT
            # series — complete where these have gaps (`tick_gap_forced_commit`)
            # — and may not exist in storage at all, since a Realtime run only
            # ever syncs/coverage-checks `tick_resolution`, never `timeframe`.
            # Drawing published candles beneath markers derived from these
            # would show a chart disagreeing with the decisions actually made.
            raw_klines = list(result.committed_bars)
            self._log_dev_trace(
                "chart_source_committed_bars",
                timeframe=config.timeframe.value,
                bars=len(raw_klines),
            )
        else:
            try:
                query = GetHistoricalKlinesQuery(
                    symbol=self._symbol,
                    interval=config.timeframe.value,
                    limit=self._chart_klines_fetch_limit,
                    start_time=config.start_time,
                    end_time=config.end_time,
                    # Descending + reversed below (mirrors dashboard_presenter's
                    # own _run_load_history) so a range with more than
                    # the fetch limit keeps the MOST RECENT ones —
                    # ascending order would silently cap at the OLDEST instead.
                    order_by_desc=True,
                )
                self._log_dev_trace(
                    "chart_query_dispatch",
                    symbol=self._symbol,
                    timeframe=config.timeframe.value,
                    limit=self._chart_klines_fetch_limit,
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

        if len(raw_klines) >= self._chart_klines_fetch_limit:
            logger.warning(
                "Backtest chart truncated to the %d most recent candles by "
                "%s; older trade markers will have no candles beneath them.",
                self._chart_klines_fetch_limit,
                ConfigKeys.BACKTEST_CHART_KLINES_FETCH_LIMIT.value,
            )
            self._log_dev_trace(
                "chart_query_truncated", limit=self._chart_klines_fetch_limit
            )

        mapped_klines = map_klines(raw_klines)
        mapped_volume = map_volume(raw_klines)
        self._log_dev_trace(
            "chart_query_ready",
            raw_klines=len(raw_klines),
            mapped_klines=len(mapped_klines),
            mapped_volume=len(mapped_volume),
        )
        self._chartDataReadySignal.emit(
            action_id, result, mapped_klines, mapped_volume, raw_klines
        )

        self._emit_strategy_indicator_lines(action_id, config, raw_klines)
        self._emit_strategy_trend_zones(action_id, config, raw_klines)

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
        colors = assign_strategy_line_colors(
            list(lines.keys()), strategy.chart_line_colors()
        )
        widths = strategy.chart_line_widths()
        for name, (x_data, y_data) in lines.items():
            self._chartStrategyLineSignal.emit(
                action_id,
                name,
                colors[name],
                x_data,
                y_data,
                widths.get(name, _DEFAULT_STRATEGY_LINE_WIDTH),
            )

    def _emit_strategy_trend_zones(
        self, action_id: int, config: BacktestRunConfig, raw_klines: list
    ) -> None:
        """
        @brief BOT-113: draws the backtested strategy's own long-term-trend
        background shading (`classify_trend_zone()`), TradingView's
        `bgcolor()` pattern.
        @details A second, separate throwaway strategy instance from
        `_emit_strategy_indicator_lines()` — that one's indicators are
        already fully replayed to the end of `raw_klines` by the time this
        runs, so reusing the same instance here would resume mid-warmup
        instead of starting fresh. A strategy that never overrides
        `classify_trend_zone()` (every strategy predating BOT-113) computes
        an empty span list — one no-op signal emit, no zones drawn, chart
        looks exactly as it did before this feature existed.
        """
        strategy_cls = self._strategy_registry.available().get(config.strategy_key)
        if strategy_cls is None:
            return
        strategy = strategy_cls(config.strategy_params)
        spans = compute_strategy_trend_zones(strategy, raw_klines)
        self._chartStrategyRegionSignal.emit(action_id, spans)
