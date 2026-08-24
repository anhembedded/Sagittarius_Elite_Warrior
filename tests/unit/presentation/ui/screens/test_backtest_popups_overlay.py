"""EPIC-006E3: `BackTestModals.qml`'s 11 modals -> `Overlay`-based
`QDialog`s owned by `BackTestModalsHost`. Originally a regression test for
the popups-clipping bug (BOT-088/BUG-004) that `OverlayHost` fixed — no
longer applicable now that each modal is a real top-level `QDialog`
(clipping by a small host widget is structurally impossible), so these
assert each modal opens (built lazily, becomes visible) and exposes the
right content, not overlay-host geometry.
"""

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
        self.slow_period = self.input_int(
            "slow_period", 50, label="Slow Period", minval=1, maxval=300
        )
        self.signal_period = self.input_int(
            "signal_period", 9, label="Signal Period", minval=1, maxval=50
        )

    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


@pytest.fixture
def backtest_screen(qapp, request):
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
    return view, presenter


def test_bot_params_dialog_opens_with_the_strategys_declared_params(
    qapp, backtest_screen
):
    view, _ = backtest_screen

    view.top_widget._btn_bot_params.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_properties
    assert dialog is not None
    assert dialog.objectName() == "botParamsDialog"
    assert dialog.isVisible() is True
    assert len(dialog._field_widgets) == 3
    assert {fw.field_name for fw in dialog._field_widgets} == {
        "period",
        "slow_period",
        "signal_period",
    }


def test_extended_metrics_popup_opens_with_the_extended_stat_cards(
    qapp, backtest_screen
):
    view, presenter = backtest_screen
    presenter._view_model.set_stat_cards(
        [],
        [
            {"title": "Card 1", "value": "100", "suffix": ""},
            {"title": "Card 2", "value": "200", "suffix": ""},
        ],
    )
    qapp.processEvents()

    presenter._view_model.requestOpenExtendedMetrics()
    qapp.processEvents()

    dialog = view._modals_host._extended_metrics
    assert dialog is not None
    assert dialog.objectName() == "extendedMetricsPopup"
    assert dialog.isVisible() is True
    assert dialog._grid.count() == 2


def test_limitations_popup_opens_with_each_limitation_as_its_own_label(
    qapp, backtest_screen
):
    view, presenter = backtest_screen
    presenter._view_model.set_limitations(["Limitation 1", "Limitation 2"])
    qapp.processEvents()

    view.top_widget._btn_limitations.click()
    qapp.processEvents()

    dialog = view._modals_host._limitations
    assert dialog is not None
    assert dialog.objectName() == "limitationsPopup"
    assert dialog.isVisible() is True
    assert dialog._list_layout.count() == 2


def test_capital_popup_opens_with_the_capital_field_populated(qapp, backtest_screen):
    view, _ = backtest_screen

    view.top_widget._btn_capital.click()
    qapp.processEvents()

    dialog = view._modals_host._capital
    assert dialog is not None
    assert dialog.objectName() == "capitalDialog"
    assert dialog.isVisible() is True
    assert dialog._capital_input.objectName() == "txtBacktestCapital"
    assert dialog._capital_input.text() != ""


def test_indicator_picker_menu_opens(qapp, backtest_screen):
    view, _ = backtest_screen

    view.top_widget._btn_indicator_picker.click()
    qapp.processEvents()

    dialog = view._modals_host._indicator_picker
    assert dialog is not None
    assert dialog.objectName() == "indicatorPickerModal"
    assert dialog.isVisible() is True


def test_order_execution_menu_opens(qapp, backtest_screen):
    view, _ = backtest_screen

    view.top_widget._btn_order_exec.click()
    qapp.processEvents()

    dialog = view._modals_host._order_execution
    assert dialog is not None
    assert dialog.objectName() == "orderExecutionModal"
    assert dialog.isVisible() is True


def test_strategy_picker_modal_opens_and_lists_the_registered_strategy(
    qapp, backtest_screen
):
    view, _ = backtest_screen

    view.top_widget._btn_strategy.click()
    qapp.processEvents()

    dialog = view._modals_host._strategy_picker
    assert dialog is not None
    assert dialog.objectName() == "strategyPickerModal"
    assert dialog.isVisible() is True
    assert dialog._list_layout.count() == 1


def test_timeframe_picker_modal_opens_and_lists_every_timeframe_option(
    qapp, backtest_screen
):
    view, presenter = backtest_screen

    view.top_widget._btn_timeframe.click()
    qapp.processEvents()

    dialog = view._modals_host._timeframe_picker
    assert dialog is not None
    assert dialog.objectName() == "timeframePickerModal"
    assert dialog.isVisible() is True
    assert dialog._grid.count() == len(presenter._view_model.timeframeOptions)


def test_time_range_picker_modal_opens_and_lists_every_preset(qapp, backtest_screen):
    view, presenter = backtest_screen

    view.top_widget._btn_range.click()
    qapp.processEvents()

    dialog = view._modals_host._time_range_picker
    assert dialog is not None
    assert dialog.objectName() == "timeRangePickerModal"
    assert dialog.isVisible() is True
    assert dialog._list_layout.count() == len(
        presenter._view_model.timeRangePresetOptions
    )
