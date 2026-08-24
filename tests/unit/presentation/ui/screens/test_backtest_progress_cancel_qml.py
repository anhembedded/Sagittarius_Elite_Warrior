from __future__ import annotations

import os
from unittest.mock import Mock

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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class _DummyStrategy(BaseStrategy):
    def setup(self) -> None:
        pass

    def decide(self, context):
        return self.hold()

    def build_indicators(self):
        return {}


@pytest.fixture
def backtest_screen(qapp, request):
    registry = StrategyRegistry()
    registry.register("dummy_strategy", _DummyStrategy)
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


def test_progress_banner_cancel_button_in_running_and_syncing_modes(
    qapp, backtest_screen
):
    view, presenter = backtest_screen
    banner = view.top_widget._progress_banner
    cancel_btn = view.top_widget._btn_cancel_progress
    view_model = presenter._view_model

    # 1. In IDLE mode, progress banner is hidden
    assert banner.isVisible() is False

    # 2. In SYNCING mode, banner and cancel button are visible and enabled
    view_model.set_ui_mode("SYNCING")
    qapp.processEvents()

    assert banner.isVisible() is True
    assert cancel_btn.isEnabled() is True
    assert cancel_btn.text() == "Hủy"

    # Click Cancel on progress banner
    cancel_signal_called = False

    def on_cancel():
        nonlocal cancel_signal_called
        cancel_signal_called = True

    view_model.cancelBacktestRequested.connect(on_cancel)
    cancel_btn.click()
    qapp.processEvents()

    assert cancel_signal_called is True

    # 3. In CANCELLING mode, button is disabled and text is "Đang hủy..."
    view_model.set_ui_mode("CANCELLING")
    qapp.processEvents()

    assert banner.isVisible() is True
    assert cancel_btn.isEnabled() is False
    assert cancel_btn.text() == "Đang hủy..."

    # 4. In RUNNING mode, button is enabled and text is "Hủy"
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert banner.isVisible() is True
    assert cancel_btn.isEnabled() is True
    assert cancel_btn.text() == "Hủy"
