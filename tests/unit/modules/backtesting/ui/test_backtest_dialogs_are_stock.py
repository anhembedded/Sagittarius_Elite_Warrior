"""Every Backtest dialog `EPIC-033L` stage 3 rebuilt is a stock `QDialog`:
a window title naming its command, in title case, and its buttons in a
`QDialogButtonBox` (`ui-presentation-rule.md` §7). A dialog put back on a kit
overlay, with its title painted inside the window and a hand-built button
row, fails here.

The symbol and time-range pickers are shared components of `support/ui_kit`,
not this mode's; they change with the components.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QDialogButtonBox
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    CapitalDialogWidget,
    IndicatorPickerDialog,
    LimitationsDialog,
    MetricsDetailDialogWidget,
    OrderExecutionDialog,
    OutOfSampleComparisonDialog,
    ReportComparisonDialog,
    StrategyPropertiesDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Overlay

_DIALOGS = {
    CapitalDialogWidget: "Initial Capital",
    LimitationsDialog: "Limitations of This Run",
    OrderExecutionDialog: "Execution",
    IndicatorPickerDialog: "Indicators",
    MetricsDetailDialogWidget: "Metrics Detail",
    OutOfSampleComparisonDialog: "In-Sample vs Out-of-Sample",
    ReportComparisonDialog: "Compare Reports",
    StrategyPropertiesDialog: "Strategy Parameters",
}


@pytest.mark.parametrize("dialog_type", list(_DIALOGS), ids=lambda t: t.__name__)
def test_the_dialog_is_stock(qapp, dialog_type):
    dialog = dialog_type(BackTestViewModel())

    assert isinstance(dialog, QDialog)
    assert not isinstance(dialog, Overlay)
    assert dialog.windowTitle() == _DIALOGS[dialog_type]
    assert len(dialog.findChildren(QDialogButtonBox)) == 1
