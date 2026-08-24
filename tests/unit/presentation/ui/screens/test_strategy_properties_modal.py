from __future__ import annotations

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.domain.value_objects.commission_type import (
    CommissionType,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.currency import Currency
from Sagittarius_Elite_Warrior.src.domain.value_objects.position_sizing import (
    PositionSizingType,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)


class _SampleStrategy(BaseStrategy):
    def setup(self) -> None:
        self.fast = self.input_int("fast", 12, label="Fast EMA", minval=1, maxval=100)
        self.slow = self.input_int("slow", 26, label="Slow EMA", minval=1, maxval=200)

    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


@pytest.fixture
def modal_presenter(qapp, request):
    registry = StrategyRegistry()
    registry.register("sample_strategy", _SampleStrategy)
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.interfaces.i_config import IConfig
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        if interface == IThreadManager:
            return Mock()
        if interface == IDispatcher:
            return Mock()
        if interface == IConfig:
            cfg = Mock()
            cfg.get_all.return_value = {}
            cfg.get.return_value = None
            return cfg
        if interface == StrategyRegistry:
            return registry
        if interface == IndicatorScriptRegistry:
            return IndicatorScriptRegistry()
        if interface == BacktestChartHostFactory:
            return BacktestChartHostFactory()
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = BackTestView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    presenter = BackTestPresenter(view, container)
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return presenter


def test_view_model_broker_properties_defaults_and_mutation():
    vm = BackTestViewModel()
    assert vm.orderSizeType == PositionSizingType.PERCENT_OF_EQUITY.value
    assert vm.orderSizeValue == 100.0
    assert vm.orderSizeText == "100"
    assert vm.pyramiding == 1
    assert vm.commissionType == CommissionType.PERCENT.value
    assert vm.commissionValue == 0.1
    assert vm.commissionText == "0.1"
    assert vm.slippageTicks == 0
    assert vm.longLeverage == 1.0
    assert vm.shortLeverage == 1.0
    assert vm.takeProfitPctEnabled is False
    assert vm.takeProfitPctText == "2.0"

    # Test property setters
    vm.orderSizeType = "fixed_cash"
    assert vm.orderSizeType == "fixed_cash"

    vm.orderSizeText = "500.0"
    assert vm.orderSizeValue == 500.0
    assert vm.orderSizeText == "500.0"

    vm.pyramiding = 3
    assert vm.pyramiding == 3

    vm.commissionType = "cash_per_order"
    assert vm.commissionType == "cash_per_order"

    vm.commissionText = "1.5"
    assert vm.commissionValue == 1.5

    vm.slippageTicks = 5
    assert vm.slippageTicks == 5

    vm.longLeverage = 10.0
    assert vm.longLeverage == 10.0

    vm.takeProfitPctEnabled = True
    assert vm.takeProfitPctEnabled is True

    vm.takeProfitPctText = "4.0"
    assert vm.takeProfitPctText == "4.0"


def test_presenter_strategy_properties_save_updates_config_and_runs(
    qapp, modal_presenter
):
    vm = modal_presenter._view_model
    vm.selectedStrategyKey = "sample_strategy"
    modal_presenter._refresh_bot_params_schema()

    saved_emitted = False

    def on_saved():
        nonlocal saved_emitted
        saved_emitted = True

    vm.botParamsSaved.connect(on_saved)

    payload = {
        "inputs": {"fast": 15, "slow": 30},
        "properties": {
            "initial_capital": "25000",
            "currency": "USDT",
            "order_size_type": "percent_of_equity",
            "order_size_text": "25.0",
            "pyramiding": 4,
            "commission_type": "percent",
            "commission_text": "0.05",
            "slippage_ticks": 2,
            "take_profit_enabled": True,
            "take_profit_pct_text": "2.5",
        },
    }

    vm.requestStrategyPropertiesSave(payload)
    qapp.processEvents()

    assert saved_emitted is True
    assert vm.initialCapitalText == "25000"
    assert vm.selectedCurrency == "USDT"
    assert vm.orderSizeType == "percent_of_equity"
    assert vm.orderSizeValue == 25.0
    assert vm.pyramiding == 4
    assert vm.commissionType == "percent"
    assert vm.commissionValue == 0.05
    assert vm.slippageTicks == 2
    assert vm.takeProfitPctEnabled is True
    assert vm.takeProfitPctText == "2.5"

    # Check that BacktestRunConfig built by presenter contains all broker settings
    run_config = modal_presenter._build_run_config()
    assert run_config is not None
    assert run_config.initial_balance == 25000.0
    assert run_config.currency == Currency.USDT
    assert run_config.position_sizing.type == PositionSizingType.PERCENT_OF_EQUITY
    assert run_config.position_sizing.value == 25.0
    assert run_config.broker_config.pyramiding == 4
    assert run_config.broker_config.slippage_ticks == 2
    assert run_config.broker_config.commission_type == CommissionType.PERCENT
    assert run_config.broker_config.commission_value == 0.05
    assert run_config.broker_config.take_profit_pct == 2.5


def test_strategy_properties_modal_content_and_controls(qapp, modal_presenter):
    view = modal_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None

    save_btn = dialog.findChild(object, "btnBotParamsSave")
    assert save_btn is not None

    cancel_btn = dialog.findChild(object, "btnBotParamsCancel")
    assert cancel_btn is not None

    reset_btn = dialog.findChild(object, "btnResetBotParams")
    assert reset_btn is not None

    # Verify input controls exist
    prop_capital = dialog.findChild(object, "propInitialCapital")
    assert prop_capital is not None
    assert prop_capital.text() == "10000"

    prop_pyramiding = dialog.findChild(object, "propPyramiding")
    assert prop_pyramiding is not None
    assert prop_pyramiding.value() == 1

    prop_slippage = dialog.findChild(object, "propSlippageTicks")
    assert prop_slippage is not None
    assert prop_slippage.value() == 0

    # EPIC-001A: BrokerSimulationConfig.take_profit_pct had no UI control at
    # all before this — proves the port actually renders both new controls,
    # not just that the ViewModel/presenter plumbing exists.
    prop_tp_enabled = dialog.findChild(object, "propTakeProfitEnabled")
    assert prop_tp_enabled is not None
    assert prop_tp_enabled.isChecked() is False

    prop_tp_pct = dialog.findChild(object, "propTakeProfitPct")
    assert prop_tp_pct is not None
    assert prop_tp_pct.text() == "2.0"
    assert prop_tp_pct.isEnabled() is False
