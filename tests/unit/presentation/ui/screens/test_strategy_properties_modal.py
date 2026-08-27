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
from Sagittarius_Elite_Warrior.src.domain.strategies.volume_spike_flow_strategy import (
    VolumeSpikeFlowStrategy,
)
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
    registry.register("volume_spike_flow", VolumeSpikeFlowStrategy)
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


def test_editing_a_strategy_input_field_and_saving_uses_the_typed_value(
    qapp, modal_presenter
):
    """Coverage gap this closes: `test_presenter_strategy_properties_save_updates_config_and_runs`
    above only ever calls `vm.requestStrategyPropertiesSave(payload)` with a
    hand-built payload — it never exercises `save_and_rerun()`'s own read of
    the real field widgets. This drives the actual dialog: types into the
    real `_BotParamFieldWidget`'s QLineEdit and clicks the real Save button,
    so a bug in collecting live widget values (as opposed to the coordinator
    plumbing behind them) would actually get caught. Confirms the mechanism
    is sound: a user report of "changing a strategy parameter has no effect"
    is therefore NOT this — see the next test for the same check against
    `VolumeSpikeFlowStrategy` specifically."""
    vm = modal_presenter._view_model
    vm.selectedStrategyKey = "sample_strategy"
    modal_presenter._refresh_bot_params_schema()

    view = modal_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None

    fast_field = dialog.findChild(object, "fldBotParam_fast")
    assert fast_field is not None
    assert fast_field.text() == "12", "sanity: dialog opened showing the default"

    fast_field.selectAll()
    fast_field.insert("99")
    qapp.processEvents()
    assert fast_field.text() == "99", "sanity: the widget itself holds the edit"

    save_btn = dialog.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    save_btn.click()
    qapp.processEvents()

    # save_and_rerun() collects every declared field, not only the one
    # edited — "slow" keeps its own default (26), untouched.
    assert modal_presenter._strategy_params == {"fast": 99, "slow": 26}


def test_editing_volume_spike_flow_strategy_trailing_stop_and_saving_uses_the_typed_value(
    qapp, modal_presenter
):
    """Same round trip as the test above, against the real
    `VolumeSpikeFlowStrategy` rather than the flat, groupless `_SampleStrategy`
    — rules out a bug specific to its grouped fields (BOT-047's groups) or its
    mix of int/float/bool inputs, which the sample strategy's two plain ints
    can't exercise."""
    vm = modal_presenter._view_model
    vm.selectedStrategyKey = "volume_spike_flow"
    modal_presenter._refresh_bot_params_schema()

    view = modal_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None

    trailing_field = dialog.findChild(object, "fldBotParam_trailing_stop_pct")
    assert trailing_field is not None
    assert trailing_field.text() == "0.5", "sanity: dialog opened showing the default"

    trailing_field.selectAll()
    trailing_field.insert("5.0")
    qapp.processEvents()
    assert trailing_field.text() == "5.0", "sanity: the widget itself holds the edit"

    fade_checkbox = dialog.findChild(object, "fldBotParam_fade_mode")
    assert fade_checkbox is not None
    assert fade_checkbox.isChecked() is False, "sanity: default is off"
    fade_checkbox.click()
    qapp.processEvents()

    save_btn = dialog.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    save_btn.click()
    qapp.processEvents()

    saved = modal_presenter._strategy_params
    assert saved is not None
    assert saved["trailing_stop_pct"] == 5.0
    assert saved["fade_mode"] is True

    # And the saved dict actually constructs a strategy with the new values —
    # not just a dict that looks right but is never consumed correctly.
    strategy = VolumeSpikeFlowStrategy(saved)
    assert strategy._trailing_stop_pct == 5.0
    assert strategy._fade_mode is True


def test_pressing_enter_in_order_size_field_commits_the_typed_value(
    qapp, modal_presenter
):
    """BUG-064: user-reported symptom was "I typed a new order size, pressed
    Enter, and it still reads the old value (100), not what I typed (10)".

    Root cause was `propOrderSizeValue` (a bare QLineEdit, see
    `_build_properties_tab()`) having no `editingFinished`/`returnPressed`
    connection at all — Enter did nothing beyond leaving focus in the field.
    Nothing on the Broker Properties tab reached the ViewModel until the
    "Lưu & Chạy lại" button was clicked, so typing a value and hitting Enter
    (the ordinary "submit a form" gesture almost everywhere else) silently
    did nothing, and the next `open_for_strategy()` re-read the untouched
    ViewModel and looked like the edit had been reverted.

    Fixed via one general mechanism (`_wire_line_edits_to_save_on_focus_lost`)
    rather than a one-off connection on this one field: every `QLineEdit` in
    both tabs now commits on `editingFinished`, which fires on Enter AND on
    losing focus (see the next test for the pure focus-loss case, no Enter
    at all).
    """
    view = modal_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None
    dialog._tabs.setCurrentIndex(1)  # "Đặc tính" (Properties) tab
    qapp.processEvents()

    order_size_field = dialog.findChild(object, "propOrderSizeValue")
    assert order_size_field is not None
    assert order_size_field.text() == "100", "sanity: default order size"

    order_size_field.selectAll()
    order_size_field.insert("10")
    qapp.processEvents()
    assert order_size_field.text() == "10", "the widget itself holds the typed value"

    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    QTest.keyClick(order_size_field, Qt.Key.Key_Return)
    qapp.processEvents()

    assert modal_presenter._view_model.orderSizeText == "10"

    # Reopening must show the value that was actually committed, not revert.
    dialog.open_for_strategy(modal_presenter._view_model.selectedStrategyName)
    qapp.processEvents()
    reopened_field = dialog.findChild(object, "propOrderSizeValue")
    assert reopened_field.text() == "10"


def test_tabbing_away_from_a_field_without_pressing_enter_also_commits_it(
    qapp, modal_presenter
):
    """ "lost focus thì update" — the general mechanism must fire on losing
    focus alone, with no Enter keypress at all, since that's how a user
    tabbing (or clicking) between fields actually interacts with a form."""
    view = modal_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None
    dialog._tabs.setCurrentIndex(1)  # "Đặc tính" (Properties) tab
    qapp.processEvents()

    order_size_field = dialog.findChild(object, "propOrderSizeValue")
    commission_field = dialog.findChild(object, "propCommissionValue")
    assert order_size_field is not None
    assert commission_field is not None

    order_size_field.setFocus()
    qapp.processEvents()
    order_size_field.selectAll()
    order_size_field.insert("42")
    qapp.processEvents()

    # Moving focus to a different field — no Enter anywhere — must itself
    # commit the edited field's value.
    commission_field.setFocus()
    qapp.processEvents()

    assert modal_presenter._view_model.orderSizeText == "42"
    # BUG-064 follow-up, caught by a user immediately after the first fix
    # landed: save_and_rerun()'s success path emits botParamsSaved, which is
    # connected to self.accept() so the "Lưu & Chạy lại" BUTTON closes the
    # dialog — merely losing focus while tabbing between fields must not
    # trigger that same close.
    assert dialog.isVisible()


def test_editing_a_strategy_input_field_and_losing_focus_also_commits_it(
    qapp, modal_presenter
):
    """The same focus-loss mechanism must apply to the "Các đầu vào" tab's
    dynamically-built fields too, not only the static Properties tab — this
    is what makes it "một cơ chế chung" rather than a fix scoped to the one
    field the user happened to hit."""
    vm = modal_presenter._view_model
    vm.selectedStrategyKey = "sample_strategy"
    modal_presenter._refresh_bot_params_schema()

    view = modal_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None

    fast_field = dialog.findChild(object, "fldBotParam_fast")
    assert fast_field is not None

    fast_field.setFocus()
    qapp.processEvents()
    fast_field.selectAll()
    fast_field.insert("77")
    qapp.processEvents()

    # Move focus elsewhere without pressing Enter.
    dialog.findChild(object, "propInitialCapital").setFocus()
    qapp.processEvents()

    assert modal_presenter._strategy_params == {"fast": 77, "slow": 26}
    assert dialog.isVisible(), (
        "losing focus on an input field must not close the dialog"
    )


def test_clicking_save_still_closes_the_dialog(qapp, modal_presenter):
    """Counterpart to the two focus-loss tests above: the explicit "Lưu & Chạy
    lại" button must still close the dialog exactly as before — only the
    auto-commit-on-blur path was changed to skip that."""
    view = modal_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None
    assert dialog.isVisible()

    save_btn = dialog.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    save_btn.click()
    qapp.processEvents()

    assert not dialog.isVisible()
