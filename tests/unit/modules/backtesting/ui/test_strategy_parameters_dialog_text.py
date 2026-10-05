"""What the Strategy Parameters dialog shows as text (review of PR #362): a
group title is the strategy author's words, never an access key, and the
currencies are the domain's."""

from __future__ import annotations

from PySide6.QtWidgets import QGroupBox
from Sagittarius_Elite_Warrior.src.core.contracts.param_field import (
    ParamField,
    ParamGroup,
    ParamKind,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.contracts.currency import (
    Currency,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    StrategyPropertiesDialog,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)

_PERIOD = ParamField(
    name="period", label="Period", kind=ParamKind.INT, default=14, value=14
)


def test_a_group_title_keeps_its_ampersand(qapp):
    vm = BackTestViewModel()
    vm.strategy_params.set_bot_params_groups((ParamGroup("Entry & exit", (_PERIOD,)),))
    dialog = StrategyPropertiesDialog(vm)

    dialog.open_for_strategy("Demo")

    titles = [box.title() for box in dialog._inputs_tab.findChildren(QGroupBox)]
    assert titles == ["Entry && exit"]


def test_the_currencies_are_the_domains(qapp):
    dialog = StrategyPropertiesDialog(BackTestViewModel())
    combo = dialog._properties_tab.currency

    assert [combo.itemText(i) for i in range(combo.count())] == (Currency.list_values())
