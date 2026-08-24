"""
Regression coverage for the Backtest "Thông số Chiến lược" dialog
(`StrategyPropertiesDialog`, EPIC-006E3 — `BotParamsDialog.qml` was already
dead by BOT-104; `StrategyPropertiesModal.qml` was the live one and is what
this dialog replaces). Proves clicking the real toolbar button opens the
dialog against the live ViewModel with the strategy's real declared params,
including the Up/Down-key numeric stepper `BotParamField.qml` had.
"""

import os
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.domain.strategies.base_strategy import BaseStrategy
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)


class _RichParamsStrategy(BaseStrategy):
    def setup(self) -> None:
        self.period = self.input_int("period", 20, label="Period", minval=1, maxval=200)

    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


@pytest.fixture
def bot_params_presenter(qapp, request):
    registry = StrategyRegistry()
    registry.register("rich_strategy", _RichParamsStrategy)
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


def test_opening_bot_params_dialog_loads_real_content(qapp, bot_params_presenter):
    view = bot_params_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None
    save_btn = dialog.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    assert save_btn.isVisible() is True


def test_opening_bot_params_dialog_keeps_strategy_schema_live(
    qapp, bot_params_presenter
):
    view = bot_params_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None
    assert bot_params_presenter._view_model.botParamsSchema != []


def test_bot_params_dialog_materializes_schema_rows_for_the_open_modal(
    qapp, bot_params_presenter
):
    assert bot_params_presenter._view_model.botParamsSchema
    view = bot_params_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None
    assert dialog.objectName() == "botParamsDialog"
    assert dialog.isVisible() is True
    assert len(dialog._field_widgets) == 1
    assert dialog._field_widgets[0].field_name == "period"


def test_up_key_steps_a_visible_numeric_parameter_through_the_view_model(
    qapp, bot_params_presenter
):
    """The real key event must use Python schema normalization (BOT-104's
    `step_bot_param_value()`), not JS math — `_NumericStepLineEdit`'s port
    of `BotParamField.qml`'s `Keys.onPressed`/`WheelHandler`."""
    view = bot_params_presenter.view
    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    field = dialog.findChild(object, "fldBotParam_period")
    assert field is not None
    assert field.text() == "20"

    field.setFocus()
    QTest.keyClick(field, Qt.Key.Key_Up)
    qapp.processEvents()

    assert field.text() == "21"
