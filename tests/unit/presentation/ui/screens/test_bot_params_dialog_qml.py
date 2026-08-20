"""
Regression test for the Backtest bot-params dialog after BOT-087 moved popup
hosting into the screen's engine-owned OverlayHost.

The old field-lookup assertion no longer matches the render boundary: the
purpose here is now to prove that clicking the real toolbar button loads real
overlay content against the live ViewModel without QML parse failure, not to
re-assert the pre-BOT-087 visual tree shape.
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


def test_opening_bot_params_dialog_loads_real_content(
    qapp, qml_item, bot_params_presenter
):
    top_root = bot_params_presenter.view.top_widget.rootObject()
    btn = qml_item(top_root, "btnBacktestBotParams")
    btn.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    overlay_root = bot_params_presenter.view.overlay_host.content_item
    assert overlay_root is not None
    save_btn = overlay_root.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    assert save_btn.property("visible") is True


def test_opening_bot_params_dialog_keeps_strategy_schema_live(
    qapp, qml_item, bot_params_presenter
):
    top_root = bot_params_presenter.view.top_widget.rootObject()
    btn = qml_item(top_root, "btnBacktestBotParams")
    btn.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    overlay_root = bot_params_presenter.view.overlay_host.content_item
    assert overlay_root is not None
    save_btn = overlay_root.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    assert bot_params_presenter._view_model.botParamsSchema != []
    assert bot_params_presenter.view.top_widget.errors() == []
    assert bot_params_presenter.view.overlay_host.quick_widget.errors() == []


def test_bot_params_dialog_materializes_schema_rows_for_the_open_modal(
    qapp, qml_item, bot_params_presenter
):
    assert bot_params_presenter._view_model.botParamsSchema
    top_root = bot_params_presenter.view.top_widget.rootObject()
    qml_item(top_root, "btnBacktestBotParams").clicked.emit()
    qapp.processEvents()

    overlay_root = bot_params_presenter.view.overlay_host.content_item
    dialog = overlay_root.findChild(object, "botParamsDialog")
    assert dialog is not None
    assert dialog.property("visible") is True
    assert dialog.property("hasViewModel") is True
    assert dialog.property("parameterGroupCount") == 1
    assert dialog.property("parameterRowCount") == 2
    assert bot_params_presenter.view.overlay_host.quick_widget.errors() == []


def test_up_key_steps_a_visible_numeric_parameter_through_the_view_model(
    qapp, qml_item, bot_params_presenter
):
    """The real QML key event must use Python schema normalization, not JS math."""
    top_root = bot_params_presenter.view.top_widget.rootObject()
    qml_item(top_root, "btnBacktestBotParams").clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    overlay_root = bot_params_presenter.view.overlay_host.content_item
    dialog = overlay_root.findChild(object, "botParamsDialog")
    assert dialog is not None
    content_item = dialog.property("contentItem")
    field = qml_item(content_item, "fldBotParam_period")
    assert field is not None
    assert field.property("text") == "20"

    field.forceActiveFocus()
    QTest.keyClick(bot_params_presenter.view.overlay_host.quick_widget, Qt.Key_Up)
    qapp.processEvents()

    assert field.property("text") == "21"
