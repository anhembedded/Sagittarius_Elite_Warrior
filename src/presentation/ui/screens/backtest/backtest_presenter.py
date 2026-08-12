from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot

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
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.indicator_script_runner import (
    IndicatorScriptRunner,
    qualified_line_name,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.kline_mapping import (
    map_klines,
    map_volume,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .backtest_run_config import BacktestRunConfig
from .backtest_view_model import BackTestViewModel
from .chart_canvas_view import ChartDisplayMode
from .performance_metrics_view import (
    build_extended_stat_cards,
    build_primary_stat_cards,
    stat_cards_to_qml,
)
from .result_formatter import format_result_summary
from .time_range_preset import TimeRangePreset, resolve_time_range

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .backtest_view import BackTestView

logger = logging.getLogger("App.BackTestPresenter")

#: Mirrors dashboard_presenter.py's own `_DEFAULT_SYMBOLS` — the Backtest
#: Screen has no symbol picker yet (out of BOT-022's scope; not requested by
#: the task spec), so it backtests the same single default symbol the Dev
#: Board uses.
_DEFAULT_SYMBOL = "ETHUSDT"

_CUSTOM_TIME_FORMAT = "%Y-%m-%d %H:%M"

_INVALID_CAPITAL_MESSAGE = "Vốn ban đầu không hợp lệ: {value!r}"
_NON_POSITIVE_CAPITAL_MESSAGE = "Vốn ban đầu phải lớn hơn 0."
_INVALID_CUSTOM_START_MESSAGE = (
    f"Ngày bắt đầu không hợp lệ — định dạng {_CUSTOM_TIME_FORMAT}."
)
_INVALID_CUSTOM_RANGE_MESSAGE = "Ngày bắt đầu phải trước ngày kết thúc."
_NO_STRATEGY_MESSAGE = "Chưa có chiến lược nào được đăng ký."
_RUNNING_MESSAGE = "Đang chạy backtest..."
_ZERO_TRADES_MESSAGE = (
    "Backtest chạy xong nhưng không có giao dịch nào trong khoảng thời gian đã chọn."
)

#: The chart's "4 EMA" overlay (BOT-056 §2.2) reuses this exact registered
#: script rather than recomputing its own EMA lines — guarantees the periods
#: shown always match what the Dev Board calls "EMA Ribbon 20/50/100/200",
#: with no risk of drifting out of sync with it.
_CHART_EMA_SCRIPT_KEY = "ema_ribbon"

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


def _discard_region(key: str, spans: list) -> None:
    """`ema_ribbon` never calls `self.shade()` — this callback exists only
    because `IndicatorScriptRunner`'s constructor requires one."""


def _discard_info(key: str, fields: list) -> None:
    """`ema_ribbon` never calls `self.info()` — see `_discard_region`."""


def _discard_markers(key: str, markers: list) -> None:
    """`ema_ribbon` never calls `self.mark()` — see `_discard_region`."""


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

    INITIAL_STATE = UIMode.IDLE

    _backtestSucceededSignal = Signal(object)  # BacktestResult
    _backtestEmptySignal = Signal(str)  # message (no data, or 0 trades)
    _backtestFailedSignal = Signal(str)  # error message
    _chartDataReadySignal = Signal(object, list, list)  # result, klines, volume
    _chartEmaLineSignal = Signal(str, list, list)  # qualified_name, x_data, y_data

    def __init__(self, view: BackTestView, container: IContainer) -> None:
        super().__init__(view, container)

        self._strategy_registry: StrategyRegistry = container.resolve(StrategyRegistry)
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)
        self._script_registry: IndicatorScriptRegistry = container.resolve(
            IndicatorScriptRegistry
        )
        # Batch-only (BOT-056): rebuild()+feed_all() once per run, never
        # feed()'d incrementally — a backtest's candles are already all in
        # hand, unlike the Dev Board's live/replay feed this class mirrors.
        self._chart_script_runner = IndicatorScriptRunner(
            registry=self._script_registry,
            emit_line=self._chartEmaLineSignal.emit,
            emit_region=_discard_region,
            emit_info=_discard_info,
            emit_markers=_discard_markers,
            on_error=logger.warning,
        )

        self._view_model = BackTestViewModel()
        view.set_view_model(self._view_model)
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

        if self.fsm:
            self.fsm.add_transition(UIMode.IDLE, UIMode.LOCKED)
            self.fsm.add_transition(UIMode.LOCKED, UIMode.IDLE)
            self.fsm.add_transition(UIMode.LOCKED, UIMode.ERROR)
            self.fsm.add_transition(UIMode.ERROR, UIMode.IDLE)

        # Must be called explicitly at the end of __init__ per BasePresenter
        # contract, and before load_qml() so QML parses against a ready model.
        self._connect_ui_signals()
        self._connect_engine_events()

        # After render_symbol_cards(): view.chart_controls doesn't exist
        # until the ChartCard it's attached to has been built.
        view.render_symbol_cards([_DEFAULT_SYMBOL])
        self._connect_chart_controls()
        view.load_qml()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        self._view_model.runBacktestRequested.connect(self._on_run_backtest)
        self._backtestSucceededSignal.connect(self._on_backtest_succeeded)
        self._backtestEmptySignal.connect(self._on_backtest_empty)
        self._backtestFailedSignal.connect(self._on_backtest_failed)
        self._chartDataReadySignal.connect(self._on_chart_data_ready)
        self._chartEmaLineSignal.connect(self._on_chart_ema_line)

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
        chart-mutation logic (which needs `self._chart_script_runner`'s
        state) lives here, not in the View."""
        controls = self.view.chart_controls
        if controls is None:
            return
        controls.sig_mode_changed.connect(self._on_chart_mode_changed)
        controls.sig_ema_toggled.connect(self._on_ema_toggled)
        controls.sig_volume_toggled.connect(self.view.set_volume_visible)
        controls.sig_trade_flags_toggled.connect(self.view.set_trade_flags_visible)

    # ================================================================== #
    # Qt Slots — main thread
    # ================================================================== #

    @Slot()
    @safe_ui_action
    def _on_run_backtest(self) -> None:
        if self.fsm.current_state != UIMode.IDLE:
            return
        config = self._build_run_config()
        if config is None:
            return

        self.fsm.transition_to(UIMode.LOCKED)
        self._view_model.set_result(_RUNNING_MESSAGE, is_error=False)
        self._thread_manager.submit(self._run_backtest, config)

    @Slot(object)
    @safe_ui_action
    def _on_backtest_succeeded(self, result: BacktestResult) -> None:
        """Fires for every real `BacktestResult`, trades or not — stat cards
        (BOT-055) always populate from it (0 trades means every card reads
        0/neutral, never "no cards"); only the status message differs."""
        self._view_model.set_stat_cards(
            stat_cards_to_qml(build_primary_stat_cards(result)),
            stat_cards_to_qml(build_extended_stat_cards(result)),
        )
        message = (
            format_result_summary(result)
            if result.trades
            else f"{_ZERO_TRADES_MESSAGE}\n\n{format_result_summary(result)}"
        )
        self._view_model.set_result(message, is_error=False)
        self.fsm.transition_to(UIMode.IDLE)

    @Slot(str)
    @safe_ui_action
    def _on_backtest_empty(self, message: str) -> None:
        """Only for "no historical data at all" — there is no `BacktestResult`
        to build stat cards from, so the panel is cleared."""
        self._view_model.set_stat_cards([], [])
        self._view_model.set_result(message, is_error=False)
        self.fsm.transition_to(UIMode.IDLE)

    @Slot(str)
    @safe_ui_action
    def _on_backtest_failed(self, message: str) -> None:
        self._view_model.set_stat_cards([], [])
        self._view_model.set_result(f"Lỗi: {message}", is_error=True)
        self.fsm.transition_to(UIMode.IDLE)

    @Slot(object, list, list)
    @safe_ui_action
    def _on_chart_data_ready(
        self, result: BacktestResult, klines: list, volume: list
    ) -> None:
        self.view.on_backtest_data_ready(result, klines, volume)

    @Slot(str, list, list)
    @safe_ui_action
    def _on_chart_ema_line(self, name: str, x_data: list, y_data: list) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        if card is not None:
            self._chart_script_runner.draw(card, name, x_data, y_data)

    @Slot(str)
    @safe_ui_action
    def _on_chart_mode_changed(self, mode_value: str) -> None:
        mode = ChartDisplayMode(mode_value)
        self.view.set_chart_mode(mode)
        # Entry/exit PRICE markers don't mean anything once the main plot is
        # showing Equity instead of price — see BacktestChartControls'
        # set_trade_flags_enabled docstring.
        self.view.chart_controls.set_trade_flags_enabled(
            mode is not ChartDisplayMode.EQUITY
        )

    @Slot(bool)
    @safe_ui_action
    def _on_ema_toggled(self, visible: bool) -> None:
        card = self.view.chart_cards[0] if self.view.chart_cards else None
        active = self._chart_script_runner.active.get(_CHART_EMA_SCRIPT_KEY)
        if card is None or active is None:
            return
        for line_name in active.registered_lines:
            card.set_indicator_visible(
                qualified_line_name(_CHART_EMA_SCRIPT_KEY, line_name), visible
            )

    # ================================================================== #
    # Main-thread helpers
    # ================================================================== #

    def _build_run_config(self) -> BacktestRunConfig | None:
        """Reads and validates the toolbar fields. Returns `None` (having
        already reported the error) rather than raising — mirrors
        `SettingsPresenter._on_save`'s validate-before-any-side-effect shape."""
        view_model = self._view_model

        try:
            initial_balance = float(view_model.initialCapitalText)
        except ValueError:
            view_model.set_result(
                _INVALID_CAPITAL_MESSAGE.format(value=view_model.initialCapitalText),
                is_error=True,
            )
            return None
        if initial_balance <= 0:
            view_model.set_result(_NON_POSITIVE_CAPITAL_MESSAGE, is_error=True)
            return None

        if not view_model.selectedStrategyKey:
            view_model.set_result(_NO_STRATEGY_MESSAGE, is_error=True)
            return None

        preset = TimeRangePreset(view_model.timeRangePreset)
        custom_start: datetime | None = None
        custom_end: datetime | None = None
        if preset is TimeRangePreset.CUSTOM:
            custom_start = _parse_custom_datetime(view_model.customStartText)
            if custom_start is None:
                view_model.set_result(_INVALID_CUSTOM_START_MESSAGE, is_error=True)
                return None
            custom_end = _parse_custom_datetime(view_model.customEndText)
            if custom_end is not None and custom_start >= custom_end:
                view_model.set_result(_INVALID_CUSTOM_RANGE_MESSAGE, is_error=True)
                return None

        start_time, end_time = resolve_time_range(
            preset, datetime.now(UTC), custom_start, custom_end
        )

        return BacktestRunConfig(
            strategy_key=view_model.selectedStrategyKey,
            timeframe=TimeFrame(view_model.selectedTimeframe),
            initial_balance=initial_balance,
            start_time=start_time,
            end_time=end_time,
        )

    # ================================================================== #
    # Background method — submitted to IThreadManager.
    # MUST NOT touch the view model directly. Signals only.
    # ================================================================== #

    def _run_backtest(self, config: BacktestRunConfig) -> None:
        try:
            command = RunStaticBacktestCommand(
                symbol=_DEFAULT_SYMBOL,
                interval=config.timeframe,
                strategy_key=config.strategy_key,
                initial_balance=config.initial_balance,
                start_time=config.start_time,
                end_time=config.end_time,
            )
            result = self.dispatcher.dispatch(RunStaticBacktestCommand, command)
        except Exception as exc:
            logger.exception("Static backtest failed")
            self._backtestFailedSignal.emit(str(exc))
            return

        if result is None:
            self._backtestEmptySignal.emit(
                f"Không có dữ liệu lịch sử cho {_DEFAULT_SYMBOL} "
                f"({config.timeframe.value}). Hãy sync dữ liệu trước."
            )
            return

        # Emitted whether or not there are trades — _on_backtest_succeeded
        # always has a real BacktestResult to build stat cards from; only
        # "no historical data at all" (result is None, above) has none.
        self._backtestSucceededSignal.emit(result)
        self._fetch_and_emit_chart_data(config, result)

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
                symbol=_DEFAULT_SYMBOL,
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
            response = self.dispatcher.dispatch(GetHistoricalKlinesQuery, query)
            raw_klines = list(reversed(getattr(response, "data", response) or []))
        except Exception:
            logger.exception("Fetching chart klines failed")
            return

        if not raw_klines:
            return

        mapped_klines = map_klines(raw_klines)
        mapped_volume = map_volume(raw_klines)
        self._chartDataReadySignal.emit(result, mapped_klines, mapped_volume)

        self._chart_script_runner.rebuild([_CHART_EMA_SCRIPT_KEY])
        self._chart_script_runner.feed_all(raw_klines)
