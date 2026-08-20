"""
Regression test reproducing the Backtest popups clipping bug (BOT-088 / BUG-004).
Asserts that toolbar dialogs/popups (BotParamsDialog, limitationsPopup,
extendedMetricsPopup, capitalPopup) are hosted in OverlayHost covering the full
window (1400x800) and are not clipped within top_widget's 190px height budget.
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


def test_bot_params_dialog_opens_in_overlay_host_without_clipping(
    qapp, qml_item, backtest_screen
):
    view, _ = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    assert overlay_host.content_item is not None
    assert overlay_host.overlay_size[1] >= 800
    assert overlay_host.is_click_through is True

    # Click Thông số Bot button on toolbar
    btn_bot_params = qml_item(top_root, "btnBacktestBotParams")
    assert btn_bot_params is not None
    btn_bot_params.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    # Modal must be open in overlay_host, capturing mouse input
    assert overlay_host.is_click_through is False

    # The save button must be inside overlay content and visible
    overlay_root = overlay_host.content_item
    save_btn = overlay_root.findChild(object, "btnBotParamsSave")
    assert save_btn is not None
    assert save_btn.property("visible") is True

    # The save button's global Y coordinate must be outside top_widget (height ~190px),
    # proving the dialog extends into the full window without being clipped by top_widget
    save_pos = save_btn.mapToItem(overlay_root, 0, 0)
    assert save_pos.y() > view.top_widget.height()


def test_extended_metrics_popup_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, presenter = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    presenter._view_model.set_stat_cards(
        [],
        [
            {"title": "Card 1", "value": "100", "suffix": ""},
            {"title": "Card 2", "value": "200", "suffix": ""},
        ],
    )
    qapp.processEvents()

    # Click Mở rộng chỉ số chi tiết link
    expand_link = top_root.findChild(object, "lnkExpandMetrics")
    assert expand_link is not None
    presenter._view_model.requestOpenExtendedMetrics()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False
    overlay_root = overlay_host.content_item
    popup = overlay_root.findChild(object, "extendedMetricsPopup")
    assert popup is not None
    assert popup.property("visible") is True


def test_limitations_popup_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, presenter = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    presenter._view_model.set_limitations(["Limitation 1", "Limitation 2"])
    qapp.processEvents()

    btn_limitations = qml_item(top_root, "btnBacktestLimitations")
    assert btn_limitations is not None
    btn_limitations.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False
    overlay_root = overlay_host.content_item
    popup = overlay_root.findChild(object, "limitationsPopup")
    assert popup is not None
    assert popup.property("visible") is True


def test_capital_popup_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, _ = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    btn_capital = qml_item(top_root, "btnBacktestCapital")
    assert btn_capital is not None
    btn_capital.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False
    overlay_root = overlay_host.content_item
    txt_capital = overlay_root.findChild(object, "txtBacktestCapital")
    assert txt_capital is not None
    assert txt_capital.property("visible") is True


def test_indicator_picker_menu_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, _ = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    btn_picker = qml_item(top_root, "btnBacktestIndicatorPicker")
    assert btn_picker is not None
    btn_picker.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False


def test_order_execution_menu_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, _ = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    btn_order_exec = qml_item(top_root, "btnBacktestOrderExecution")
    assert btn_order_exec is not None
    btn_order_exec.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False


def test_strategy_picker_modal_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, _ = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    btn_strategy = qml_item(top_root, "btnBacktestStrategy")
    assert btn_strategy is not None
    btn_strategy.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False
    overlay_root = overlay_host.content_item
    modal = overlay_root.findChild(object, "strategyPickerModal")
    assert modal is not None
    assert modal.property("visible") is True


def test_timeframe_picker_modal_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, _ = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    btn_timeframe = qml_item(top_root, "btnBacktestTimeframe")
    assert btn_timeframe is not None
    btn_timeframe.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False
    overlay_root = overlay_host.content_item
    modal = overlay_root.findChild(object, "timeframePickerModal")
    assert modal is not None
    assert modal.property("visible") is True


def test_time_range_picker_modal_opens_in_overlay_host(qapp, qml_item, backtest_screen):
    view, _ = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    btn_range = qml_item(top_root, "btnBacktestRange")
    assert btn_range is not None
    btn_range.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    assert overlay_host.is_click_through is False
    overlay_root = overlay_host.content_item
    modal = overlay_root.findChild(object, "timeRangePickerModal")
    assert modal is not None
    assert modal.property("visible") is True
