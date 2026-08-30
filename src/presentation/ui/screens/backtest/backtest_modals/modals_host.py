"""Lazily builds each Backtest modal and wires it to the view model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.components.timeframe_picker import (
    TimeframePickerOverlay,
)

from .capital_dialog import CapitalDialogWidget
from .extended_metrics_dialog import ExtendedMetricsDialog
from .indicator_picker_dialog import IndicatorPickerDialog
from .limitations_dialog import LimitationsDialog
from .order_execution_dialog import OrderExecutionDialog
from .strategy_picker_dialog import StrategyPickerDialog
from .strategy_properties_dialog import StrategyPropertiesDialog
from .symbol_picker_dialog import SymbolPickerDialogWidget
from .time_range_picker_dialog import TimeRangePickerDialogWidget
from .timezone_picker_dialog import TimezonePickerDialog

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class BackTestModalsHost:
    """Owns all 11 modal `QDialog`s, built lazily on first open (matching
    every other lazy-modal precedent in this app —
    `DataManagementView._kline_inspector`, EPIC-005E2/E3), and wires
    `BackTestViewModel`'s `openXRequested` signals to them. Replaces both
    `BackTestModals.qml` and Engine's `OverlayHost`/`QQuickWidget` — a real
    `QDialog` is already modal and self-centering over its parent, so the
    full-window click-through overlay QML existed for no longer applies."""

    def __init__(self, view_model: BackTestViewModel, parent: QWidget) -> None:
        self._vm = view_model
        self._parent = parent
        self._capital: CapitalDialogWidget | None = None
        self._extended_metrics: ExtendedMetricsDialog | None = None
        self._limitations: LimitationsDialog | None = None
        self._indicator_picker: IndicatorPickerDialog | None = None
        self._order_execution: OrderExecutionDialog | None = None
        self._strategy_picker: StrategyPickerDialog | None = None
        self._timeframe_picker: TimeframePickerOverlay | None = None
        self._symbol_picker: SymbolPickerDialogWidget | None = None
        # EPIC-014: replaced in production by the container-registered store
        # (BackTestPresenter injects it through
        # `BackTestView.set_symbol_preferences`), so a star set on Backtest is
        # the same star Dev Board shows. Self-constructed here so a bare
        # `BackTestModalsHost(vm, parent)` — every existing test — still
        # opens a working picker, it just remembers nothing past the session.
        self._symbol_preferences = SymbolPreferences()
        self._time_range_picker: TimeRangePickerDialogWidget | None = None
        self._timezone_picker: TimezonePickerDialog | None = None
        self._strategy_properties: StrategyPropertiesDialog | None = None

        view_model.openCapitalRequested.connect(self._open_capital)
        view_model.openExtendedMetricsRequested.connect(self._open_extended_metrics)
        view_model.openLimitationsRequested.connect(self._open_limitations)
        view_model.openIndicatorPickerRequested.connect(self._open_indicator_picker)
        view_model.openOrderExecutionRequested.connect(self._open_order_execution)
        view_model.openStrategyPickerRequested.connect(self._open_strategy_picker)
        view_model.openTimeframePickerRequested.connect(self._open_timeframe_picker)
        view_model.openSymbolPickerRequested.connect(self._open_symbol_picker)
        view_model.openTimeRangePickerRequested.connect(self._open_time_range_picker)
        view_model.openTimezonePickerRequested.connect(self._open_timezone_picker)
        view_model.openBotParamsRequested.connect(self._open_bot_params)

    def _open_capital(self, _x: float, _y: float) -> None:
        if self._capital is None:
            self._capital = CapitalDialogWidget(self._vm, self._parent)
        self._capital.open_dialog()

    def _open_extended_metrics(self) -> None:
        if self._extended_metrics is None:
            self._extended_metrics = ExtendedMetricsDialog(self._vm, self._parent)
        self._extended_metrics.show()
        self._extended_metrics.raise_()

    def _open_limitations(self) -> None:
        if self._limitations is None:
            self._limitations = LimitationsDialog(self._vm, self._parent)
        self._limitations.show()
        self._limitations.raise_()

    def _open_indicator_picker(self, _x: float, _y: float) -> None:
        if self._indicator_picker is None:
            self._indicator_picker = IndicatorPickerDialog(self._vm, self._parent)
        self._indicator_picker.show()
        self._indicator_picker.raise_()

    def _open_order_execution(self, _x: float, _y: float) -> None:
        if self._order_execution is None:
            self._order_execution = OrderExecutionDialog(self._vm, self._parent)
        self._order_execution.show()
        self._order_execution.raise_()

    def _open_strategy_picker(self) -> None:
        if self._strategy_picker is None:
            self._strategy_picker = StrategyPickerDialog(self._vm, self._parent)
        self._strategy_picker.show()
        self._strategy_picker.raise_()

    def set_symbol_preferences(self, preferences: SymbolPreferences) -> None:
        """Swaps in the shared, persisted favourites/recents store.

        @details Called by `BackTestPresenter` before the picker is first
        opened — the same injection seam `set_chart_host_factory` uses, and
        for the same reason: `BackTestView` has no container access. Unlike
        the old `SymbolPreferences.bind_picker`/`unbind_picker` dance, there
        is no Qt connection to rebind: `SymbolPickerDialogWidget` only ever
        reads the store through `BacktestSymbolPickerSource`, so swapping the
        reference the source holds is the whole update — see
        `BacktestSymbolPickerSource.set_preferences`.
        """
        if preferences is self._symbol_preferences:
            return
        if self._symbol_picker is not None:
            self._symbol_picker.set_preferences(preferences)
        self._symbol_preferences = preferences

    def _open_timeframe_picker(self) -> None:
        if self._timeframe_picker is None:
            self._timeframe_picker = TimeframePickerOverlay(
                get_options=lambda: self._vm.timeframeOptions,
                get_current=lambda: self._vm.selectedTimeframe,
                parent=self._parent,
            )
            self._timeframe_picker.timeframe_chosen.connect(self._on_timeframe_chosen)
        self._timeframe_picker.show()
        self._timeframe_picker.raise_()

    def _on_timeframe_chosen(self, code: str) -> None:
        self._vm.selectedTimeframe = code

    def _open_symbol_picker(self) -> None:
        if self._symbol_picker is None:
            self._symbol_picker = SymbolPickerDialogWidget(
                self._vm, self._symbol_preferences, self._parent
            )
            # BOT-102: the exchange list arrives after the first open, so the
            # dialog has to be told rather than left showing "Đang tải" until
            # the user closes and reopens it.
            self._vm.symbolOptionsChanged.connect(self._refresh_symbol_picker)
        self._symbol_picker.open_dialog()

    def _refresh_symbol_picker(self) -> None:
        if self._symbol_picker is not None and self._symbol_picker.isVisible():
            self._symbol_picker.refresh()

    def _open_time_range_picker(self) -> None:
        if self._time_range_picker is None:
            self._time_range_picker = TimeRangePickerDialogWidget(
                self._vm, self._parent
            )
        self._time_range_picker.open_dialog()

    def _open_timezone_picker(self) -> None:
        if self._timezone_picker is None:
            self._timezone_picker = TimezonePickerDialog(self._vm, self._parent)
        self._timezone_picker.show()
        self._timezone_picker.raise_()

    def _open_bot_params(self, strategy_name: str) -> None:
        if self._strategy_properties is None:
            self._strategy_properties = StrategyPropertiesDialog(self._vm, self._parent)
        self._strategy_properties.open_for_strategy(strategy_name)
