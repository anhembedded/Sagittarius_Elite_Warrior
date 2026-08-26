"""EPIC-006E3: Backtest's 11 modal QMLs (orchestrated by
`BackTestModals.qml`) -> `Overlay`-based `QDialog`s.

`BotParamsDialog.qml` (200 lines) was NOT ported — verified dead: never
instantiated anywhere (`BackTestModals.qml` only ever built
`StrategyPropertiesModal`, BOT-104's superseding 4-tab dialog). Porting it
would have been wasted work; `git grep 'BotParamsDialog {'` confirms zero
instantiations.

Each dialog is built lazily by `BackTestModalsHost` (this module's
orchestrator, replacing `BackTestModals.qml` + Engine's `OverlayHost`/
`QQuickWidget` — a real `QDialog` is already modal and self-positioning,
so the full-window click-through overlay QML needed no longer applies)
and wired directly to `BackTestViewModel`'s `openXRequested` signals.

Split into one file per dialog by `EPIC-007G`. This package re-exports
every name the single module used to export, so no call site changed.
"""

from __future__ import annotations

from .capital_dialog import CapitalDialogWidget
from .extended_metrics_dialog import ExtendedMetricsDialog
from .indicator_picker_dialog import IndicatorPickerDialog
from .limitations_dialog import LimitationsDialog
from .modals_host import BackTestModalsHost
from .order_execution_dialog import OrderExecutionDialog
from .strategy_picker_dialog import StrategyPickerDialog
from .strategy_properties_dialog import StrategyPropertiesDialog
from .symbol_picker_dialog import BacktestSymbolPickerDialog
from .time_range_picker_dialog import TimeRangePickerDialog
from .timeframe_picker_dialog import TimeframePickerDialog
from .timezone_picker_dialog import TimezonePickerDialog

__all__ = [
    "BackTestModalsHost",
    "BacktestSymbolPickerDialog",
    "CapitalDialogWidget",
    "ExtendedMetricsDialog",
    "IndicatorPickerDialog",
    "LimitationsDialog",
    "OrderExecutionDialog",
    "StrategyPickerDialog",
    "StrategyPropertiesDialog",
    "TimeRangePickerDialog",
    "TimeframePickerDialog",
    "TimezonePickerDialog",
]
