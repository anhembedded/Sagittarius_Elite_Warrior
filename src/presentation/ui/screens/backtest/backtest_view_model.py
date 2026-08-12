from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot

from Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.chart_toolbar import (
    DEFAULT_TIMEFRAMES,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.time_range_preset import (
    TimeRangePreset,
)
from sagittarius_engine.extensions.pyside_mvc import BaseQmlViewModel

_DEFAULT_INITIAL_CAPITAL_TEXT = "10000"
_DEFAULT_TIMEFRAME = "15m"


class BackTestViewModel(BaseQmlViewModel):
    """
    @brief QML-facing state for the Backtest Screen (BOT-022).

    @details
    Deliberately holds no business logic — same split as
    `SettingsViewModel`/`SidebarViewModel`: it carries the editable config
    fields plus the result/status text, and turns a "Chạy Backtest" click
    into a `runBacktestRequested` signal for `BackTestPresenter` to act on.
    Validation, `RunStaticBacktestCommand` construction, and dispatch all
    stay in the Presenter.

    `controlsEnabled` (inherited from `BaseQmlViewModel`) drives every input
    the toolbar exposes — QML binds `enabled: viewModel.controlsEnabled`
    instead of a hand-rolled `uiMode !== "LOCKED"` check.
    """

    DISABLED_UI_MODES = frozenset({UIMode.LOCKED.value})

    strategyOptionsChanged = Signal()
    selectedStrategyKeyChanged = Signal()
    initialCapitalTextChanged = Signal()
    selectedTimeframeChanged = Signal()
    timeRangePresetChanged = Signal()
    customStartTextChanged = Signal()
    customEndTextChanged = Signal()
    resultChanged = Signal()

    #: Emitted when the user clicks "Chạy Backtest". The Presenter reads the
    #: current field values off this view model rather than receiving them
    #: as arguments, so adding a field never changes this signal's signature.
    runBacktestRequested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._strategy_options: list[dict[str, str]] = []
        self._selected_strategy_key = ""
        self._initial_capital_text = _DEFAULT_INITIAL_CAPITAL_TEXT
        self._selected_timeframe = _DEFAULT_TIMEFRAME
        self._time_range_preset = TimeRangePreset.ALL_HISTORY.value
        self._custom_start_text = ""
        self._custom_end_text = ""
        self._result_text = ""
        self._result_is_error = False

    # ------------------------------------------------------------------ #
    # Strategy selection
    # ------------------------------------------------------------------ #

    def _get_strategy_options(self) -> list[dict[str, str]]:
        return self._strategy_options

    #: list[{"key": ..., "name": ...}] — read-only from QML, written once
    #: (per screen construction) from `StrategyRegistry.available()`.
    strategyOptions = Property(
        "QVariantList", _get_strategy_options, notify=strategyOptionsChanged
    )

    def set_strategy_options(self, options: list[dict[str, str]]) -> None:
        self._strategy_options = options
        self.strategyOptionsChanged.emit()
        if options and not self._selected_strategy_key:
            self._set_selected_strategy_key(options[0]["key"])

    def _get_selected_strategy_key(self) -> str:
        return self._selected_strategy_key

    def _set_selected_strategy_key(self, value: str) -> None:
        if value != self._selected_strategy_key:
            self._selected_strategy_key = value
            self.selectedStrategyKeyChanged.emit()

    selectedStrategyKey = Property(
        str,
        _get_selected_strategy_key,
        _set_selected_strategy_key,
        notify=selectedStrategyKeyChanged,
    )

    # ------------------------------------------------------------------ #
    # Capital / timeframe
    # ------------------------------------------------------------------ #

    def _get_initial_capital_text(self) -> str:
        return self._initial_capital_text

    def _set_initial_capital_text(self, value: str) -> None:
        if value != self._initial_capital_text:
            self._initial_capital_text = value
            self.initialCapitalTextChanged.emit()

    initialCapitalText = Property(
        str,
        _get_initial_capital_text,
        _set_initial_capital_text,
        notify=initialCapitalTextChanged,
    )

    @Property("QStringList", constant=True)
    def timeframeOptions(self) -> list[str]:
        return list(DEFAULT_TIMEFRAMES)

    def _get_selected_timeframe(self) -> str:
        return self._selected_timeframe

    def _set_selected_timeframe(self, value: str) -> None:
        if value != self._selected_timeframe:
            self._selected_timeframe = value
            self.selectedTimeframeChanged.emit()

    selectedTimeframe = Property(
        str,
        _get_selected_timeframe,
        _set_selected_timeframe,
        notify=selectedTimeframeChanged,
    )

    # ------------------------------------------------------------------ #
    # Time range
    # ------------------------------------------------------------------ #

    @Property("QVariantList", constant=True)
    def timeRangePresetOptions(self) -> list[dict[str, str]]:
        return [
            {"value": TimeRangePreset.LAST_7_DAYS.value, "label": "7 ngày qua"},
            {"value": TimeRangePreset.LAST_30_DAYS.value, "label": "30 ngày qua"},
            {"value": TimeRangePreset.LAST_90_DAYS.value, "label": "90 ngày qua"},
            {"value": TimeRangePreset.LAST_365_DAYS.value, "label": "365 ngày qua"},
            {"value": TimeRangePreset.ALL_HISTORY.value, "label": "Toàn bộ lịch sử"},
            {"value": TimeRangePreset.CUSTOM.value, "label": "Tuỳ chỉnh"},
        ]

    def _get_time_range_preset(self) -> str:
        return self._time_range_preset

    def _set_time_range_preset(self, value: str) -> None:
        if value != self._time_range_preset:
            self._time_range_preset = value
            self.timeRangePresetChanged.emit()

    timeRangePreset = Property(
        str,
        _get_time_range_preset,
        _set_time_range_preset,
        notify=timeRangePresetChanged,
    )

    def _get_custom_start_text(self) -> str:
        return self._custom_start_text

    def _set_custom_start_text(self, value: str) -> None:
        if value != self._custom_start_text:
            self._custom_start_text = value
            self.customStartTextChanged.emit()

    customStartText = Property(
        str,
        _get_custom_start_text,
        _set_custom_start_text,
        notify=customStartTextChanged,
    )

    def _get_custom_end_text(self) -> str:
        return self._custom_end_text

    def _set_custom_end_text(self, value: str) -> None:
        if value != self._custom_end_text:
            self._custom_end_text = value
            self.customEndTextChanged.emit()

    customEndText = Property(
        str, _get_custom_end_text, _set_custom_end_text, notify=customEndTextChanged
    )

    # ------------------------------------------------------------------ #
    # Result / status (written from Python only)
    # ------------------------------------------------------------------ #

    def _get_result_text(self) -> str:
        return self._result_text

    resultText = Property(str, _get_result_text, notify=resultChanged)

    def _get_result_is_error(self) -> bool:
        return self._result_is_error

    resultIsError = Property(bool, _get_result_is_error, notify=resultChanged)

    def set_result(self, text: str, is_error: bool) -> None:
        self._result_text = text
        self._result_is_error = is_error
        self.resultChanged.emit()

    # ------------------------------------------------------------------ #
    # QML entry point
    # ------------------------------------------------------------------ #

    @Slot()
    def requestRun(self) -> None:
        """Called from QML's "Chạy Backtest" button."""
        self.runBacktestRequested.emit()
