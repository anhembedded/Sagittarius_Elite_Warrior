"""
Unit test for OrderExecutionModal (BOT-074, updated by BOT-076/BOT-077,
ported to QML by EPIC-015 §4c).

BOT-074 deliberately left all 4 modes locked and predicted this test would
break "by design" once a real engine existed to unlock one — that happened
twice since: BOT-076 unlocked index 2 ("Trên mỗi tick của thanh lịch sử",
the Realtime/tick-driven engine), wired to
`BackTestViewModel.executionMode` -> `BacktestRunConfig.execution_mode` ->
`RunHistoricalTickBacktestCommand` dispatch; BOT-077 unlocks index 1 ("Khi
lệnh được khớp"), wired the same way through
`BackTestViewModel.calcOnOrderFills` -> `BacktestRunConfig.calc_on_order_fills`
-> `RunHistoricalTickBacktestCommand.calc_on_order_fills`.

Truthful lock states now:
- Index 0 ("On bar close", BOT-021 static engine) — checked by default,
  locked (mandatory; the user leaves it by picking index 2 instead, not by
  unchecking it directly, same as any 2-option radio group).
- Index 1 ("Khi lệnh được khớp", BOT-077) — unlocked, real; only takes
  effect while index 2 is also active (`calc_on_order_fills` is meaningless
  in `BAR_CLOSE` mode — see the command's own docstring).
- Index 2 ("Trên mỗi tick của thanh lịch sử", BOT-076) — unlocked, real.
- Index 3 ("Trên mỗi tick của thanh thời gian thực") stays locked — it means
  a live/real-time bar (Dev Board), and this modal only ever opens from the
  Backtest screen. If a later task unlocks it, THIS test should fail again
  "by design" the same way BOT-074's did — do not weaken the loop below to
  silently accept it.

`EPIC-033L` gives the two exclusive triggers their stock shape, radio buttons
(`ui-presentation-rule.md` §6): "On bar close" is no longer a locked box left
only by checking its rival, it is a choice. "On order fill" is a check box,
and the real-time row stays locked and checked, the failure "by design" the
paragraph above asks for if it ever unlocks.
"""

from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_catalog_service import (
    StrategyCatalogService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_chart_overlay_service import (
    StrategyChartOverlayService,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_catalog import (
    IStrategyCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.contracts.i_strategy_chart_overlay import (
    IStrategyChartOverlay,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from sagittarius_engine.interfaces.i_config import IConfig
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

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
        if interface == IStrategyCatalog:
            return StrategyCatalogService(registry)
        if interface == IStrategyChartOverlay:
            return StrategyChartOverlayService(registry)
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
    _ = BackTestPresenter(view, container)
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return view


#: index -> expected (locked, initially checked). Index 2 is BOT-076's real
#: mode; everything else is exactly BOT-074's original truthful lock state.
def _open_order_execution_modal(qapp, view):
    view.run_setup.execution.click()
    qapp.processEvents()

    dialog = view._modals_host._order_execution
    assert dialog is not None, "OrderExecutionDialog not built"
    assert dialog.isVisible() is True
    return dialog


def test_the_defaults_are_bar_close_without_order_fill(qapp, backtest_screen):
    dialog = _open_order_execution_modal(qapp, backtest_screen)

    assert dialog.bar_close.isChecked() is True
    assert dialog.historical_tick.isChecked() is False
    assert dialog.order_fill.isChecked() is False
    assert all(
        control.isEnabled()
        for control in (dialog.bar_close, dialog.historical_tick, dialog.order_fill)
    )


def test_the_real_time_row_stays_locked_and_checked(qapp, backtest_screen):
    """A live-trading fact the Backtest mode cannot change; if a later task
    unlocks it, this fails by design (see the module docstring)."""
    dialog = _open_order_execution_modal(qapp, backtest_screen)

    assert dialog.realtime_tick.isChecked() is True
    assert dialog.realtime_tick.isEnabled() is False


def test_the_two_modes_exclude_each_other_and_reach_the_view_model(
    qapp, backtest_screen
):
    """BOT-076: the choice must actually reach Python, in both directions of
    the pair."""
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)
    view_model = view._view_model
    assert view_model.executionMode == "BAR_CLOSE"

    dialog.historical_tick.click()
    qapp.processEvents()
    assert view_model.executionMode == "HISTORICAL_TICK"
    assert dialog.bar_close.isChecked() is False

    dialog.bar_close.click()
    qapp.processEvents()
    assert view_model.executionMode == "BAR_CLOSE"
    assert dialog.historical_tick.isChecked() is False


def test_setting_execution_mode_from_python_updates_the_modes(qapp, backtest_screen):
    """The reverse direction: an external reset (e.g. FSM going back to IDLE)
    must not leave the dialog showing a stale selection."""
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)

    view._view_model.executionMode = "HISTORICAL_TICK"
    qapp.processEvents()

    assert dialog.bar_close.isChecked() is False
    assert dialog.historical_tick.isChecked() is True


def test_checking_calc_on_order_fills_sets_the_view_model_flag(qapp, backtest_screen):
    """BOT-077: the order-fill box must also reach Python."""
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)

    view_model = view._view_model
    assert view_model.calcOnOrderFills is False

    dialog.order_fill.click()
    qapp.processEvents()
    assert view_model.calcOnOrderFills is True

    dialog.order_fill.click()
    qapp.processEvents()
    assert view_model.calcOnOrderFills is False


def test_setting_calc_on_order_fills_from_python_updates_the_check_box(
    qapp, backtest_screen
):
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)

    view._view_model.calcOnOrderFills = True
    qapp.processEvents()

    assert dialog.order_fill.isChecked() is True
