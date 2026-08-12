from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal, Slot

from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.backtest.run_static_backtest.command import (
    RunStaticBacktestCommand,
)
from Sagittarius_Elite_Warrior.src.domain.backtesting.backtest_result import (
    BacktestResult,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from sagittarius_engine.extensions.pyside_mvc import BasePresenter, safe_ui_action
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .backtest_run_config import BacktestRunConfig
from .backtest_view_model import BackTestViewModel
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

    INITIAL_STATE = UIMode.IDLE

    _backtestSucceededSignal = Signal(object)  # BacktestResult
    _backtestEmptySignal = Signal(str)  # message (no data, or 0 trades)
    _backtestFailedSignal = Signal(str)  # error message

    def __init__(self, view: BackTestView, container: IContainer) -> None:
        super().__init__(view, container)

        self._strategy_registry: StrategyRegistry = container.resolve(StrategyRegistry)
        self._thread_manager: IThreadManager = container.resolve(IThreadManager)

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

        view.render_symbol_cards([_DEFAULT_SYMBOL])
        view.load_qml()

    # ================================================================== #
    # BasePresenter contract implementations
    # ================================================================== #

    def _connect_ui_signals(self) -> None:
        self._view_model.runBacktestRequested.connect(self._on_run_backtest)
        self._backtestSucceededSignal.connect(self._on_backtest_succeeded)
        self._backtestEmptySignal.connect(self._on_backtest_empty)
        self._backtestFailedSignal.connect(self._on_backtest_failed)

    def _connect_engine_events(self) -> None:
        """Nothing to subscribe to: `RunStaticBacktestCommandHandler` returns
        its `BacktestResult` synchronously to the dispatch call below. It
        also emits `BacktestCompletedEvent`/`BacktestFailedEvent` on the
        event bus (for other future subscribers), but this screen already
        has its result from the return value and has no need to also listen
        for its own echo."""

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
        self._view_model.set_result(format_result_summary(result), is_error=False)
        self.fsm.transition_to(UIMode.IDLE)

    @Slot(str)
    @safe_ui_action
    def _on_backtest_empty(self, message: str) -> None:
        self._view_model.set_result(message, is_error=False)
        self.fsm.transition_to(UIMode.IDLE)

    @Slot(str)
    @safe_ui_action
    def _on_backtest_failed(self, message: str) -> None:
        self._view_model.set_result(f"Lỗi: {message}", is_error=True)
        self.fsm.transition_to(UIMode.IDLE)

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

        if not result.trades:
            self._backtestEmptySignal.emit(
                "Backtest chạy xong nhưng không có giao dịch nào trong khoảng "
                "thời gian đã chọn.\n\n" + format_result_summary(result)
            )
            return

        self._backtestSucceededSignal.emit(result)
