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

`EPIC-015` §4c moved the body to `CheckboxList.qml` and this file grew two
paragraphs about reaching items inside a `Repeater`'s scene graph. `EPIC-025`
PR 4.3f moved it back to QtWidgets, onto the shared `kit.ChecklistOverlay`, and
both paragraphs are gone with their subject: the rows are real `QCheckBox`es
again, reached through `ChecklistOverlay.checkbox_for(key)` rather than a
`findChild` that silently finds nothing. That accessor is public for this
reason — a consumer's test needs to click a row, and reaching through a private
layout is how a test starts depending on the widget's internals.

The one habit worth keeping from the QML era: look a row up **after** the state
change being checked, never hold a reference across a refresh. It costs nothing
and it is the difference between testing what is on screen and testing a stale
Python handle.
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
_EXPECTED_LOCK_STATE = {
    0: (True, True),  # On bar close — locked, mandatory default
    1: (False, False),  # Khi lệnh được khớp — BOT-077, real
    2: (False, False),  # Trên mỗi tick của thanh lịch sử — BOT-076, real
    3: (True, False),  # Trên mỗi tick của thanh thời gian thực — live, not backtest
}


def _open_order_execution_modal(qapp, view):
    view.top_widget._btn_order_exec.click()
    qapp.processEvents()

    dialog = view._modals_host._order_execution
    assert dialog is not None, "OrderExecutionDialog not built"
    assert dialog.isVisible() is True
    return dialog


def _checkbox(dialog, index: int):
    """A fresh lookup, by design — see this module's docstring."""
    return dialog.checkbox_for(str(index))


def test_order_execution_modal_lock_states_and_default_selection_are_truthful(
    qapp, backtest_screen
):
    dialog = _open_order_execution_modal(qapp, backtest_screen)

    for index, (locked, checked) in _EXPECTED_LOCK_STATE.items():
        checkbox = _checkbox(dialog, index)
        assert checkbox is not None, f"chk_{index} not found"

        assert checkbox.isChecked() is checked, (
            f"Trigger {index} checked should be {checked}, was {checkbox.isChecked()}"
        )
        assert checkbox.isEnabled() is not locked, (
            f"Trigger {index} enabled should be {not locked} "
            f"(locked={locked}), was {checkbox.isEnabled()}"
        )


def test_checking_historical_tick_mode_sets_view_model_execution_mode(
    qapp, backtest_screen
):
    """BOT-076: the one real interactive row must actually reach Python —
    exactly the plumbing gap BOT-074 documented as its own reason for
    leaving every row locked in the first place."""
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)

    view_model = view._view_model
    assert view_model.executionMode == "BAR_CLOSE"

    _checkbox(dialog, 2).click()
    qapp.processEvents()
    assert view_model.executionMode == "HISTORICAL_TICK"

    _checkbox(dialog, 2).click()
    qapp.processEvents()
    assert view_model.executionMode == "BAR_CLOSE"


def test_setting_execution_mode_from_python_updates_the_modal_checkboxes(
    qapp, backtest_screen
):
    """The reverse direction: an external reset (e.g. FSM going back to IDLE)
    must not leave the modal showing a stale selection."""
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)

    view._view_model.executionMode = "HISTORICAL_TICK"
    qapp.processEvents()

    assert _checkbox(dialog, 0).isChecked() is False
    assert _checkbox(dialog, 2).isChecked() is True


def test_checking_calc_on_order_fills_sets_the_view_model_flag(qapp, backtest_screen):
    """BOT-077: the second real interactive row must also reach Python."""
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)

    view_model = view._view_model
    assert view_model.calcOnOrderFills is False

    _checkbox(dialog, 1).click()
    qapp.processEvents()
    assert view_model.calcOnOrderFills is True

    _checkbox(dialog, 1).click()
    qapp.processEvents()
    assert view_model.calcOnOrderFills is False


def test_setting_calc_on_order_fills_from_python_updates_the_modal_checkbox(
    qapp, backtest_screen
):
    view = backtest_screen
    dialog = _open_order_execution_modal(qapp, view)

    view._view_model.calcOnOrderFills = True
    qapp.processEvents()

    assert _checkbox(dialog, 1).isChecked() is True
