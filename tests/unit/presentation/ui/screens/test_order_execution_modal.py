"""
Unit test for OrderExecutionModal (BOT-074, updated by BOT-076).

BOT-074 deliberately left all 4 modes locked and predicted this test would
break "by design" once a real engine existed to unlock one — that happened
here: BOT-076 unlocks index 2 ("Trên mỗi tick của thanh lịch sử", the
Realtime/tick-driven engine) and wires it to real Python plumbing
(`BackTestViewModel.executionMode` -> `BacktestRunConfig.execution_mode` ->
`RunRealtimeBacktestCommand` dispatch in `backtest_presenter.py`).

Truthful lock states now:
- Index 0 ("On bar close", BOT-021 static engine) — checked by default,
  locked (mandatory; the user leaves it by picking index 2 instead, not by
  unchecking it directly, same as any 2-option radio group).
- Index 2 ("Trên mỗi tick của thanh lịch sử", BOT-076) — unlocked, real.
- Index 1 ("Khi lệnh được khớp") and index 3 ("Trên mỗi tick của thanh thời
  gian thực") stay locked — index 1 is `BOT-077`'s scope (calc_on_order_fills,
  a different re-run trigger, not this engine), index 3 means a live/real-time
  bar (Dev Board), and this modal only ever opens from the Backtest screen.
  If a later task unlocks either of those, THIS test should fail again "by
  design" the same way BOT-074's did — do not weaken the loop below to
  silently accept it.
"""

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
    1: (True, False),  # Khi lệnh được khớp — BOT-077, not this task
    2: (False, False),  # Trên mỗi tick của thanh lịch sử — BOT-076, real
    3: (True, False),  # Trên mỗi tick của thanh thời gian thực — live, not backtest
}


def _open_order_execution_modal(qapp, qml_item, view):
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host
    btn_order_exec = qml_item(top_root, "btnBacktestOrderExecution")
    assert btn_order_exec is not None, "btnBacktestOrderExecution not found"
    btn_order_exec.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()

    overlay_root = overlay_host.content_item
    modal = overlay_root.findChild(object, "orderExecutionModal")
    assert modal is not None, "orderExecutionModal not found in overlay"
    assert modal.property("visible") is True
    # ModalDialogCard is a Popup, its visual root is contentItem property
    return modal.property("contentItem") or modal


def test_order_execution_modal_lock_states_and_default_selection_are_truthful(
    qapp, qml_item, backtest_screen
):
    search_root = _open_order_execution_modal(qapp, qml_item, backtest_screen)

    for index, (locked, checked) in _EXPECTED_LOCK_STATE.items():
        item = qml_item(search_root, f"chkExecutionTrigger_{index}")
        assert item is not None, f"chkExecutionTrigger_{index} not found"
        checkbox = qml_item(search_root, f"triggerCheckBox_{index}")
        assert checkbox is not None, f"triggerCheckBox_{index} not found"

        assert checkbox.property("checked") is checked, (
            f"Trigger {index} checked should be {checked}, was "
            f"{checkbox.property('checked')}"
        )
        assert item.property("enabled") is not locked, (
            f"Trigger {index} item enabled should be {not locked} "
            f"(locked={locked}), was {item.property('enabled')}"
        )
        assert checkbox.property("enabled") is not locked, (
            f"Trigger {index} checkbox enabled should be {not locked} "
            f"(locked={locked}), was {checkbox.property('enabled')}"
        )


def test_checking_historical_tick_mode_sets_view_model_execution_mode(
    qapp, qml_item, backtest_screen
):
    """BOT-076: the one real interactive row must actually reach Python —
    exactly the plumbing gap BOT-074 documented as its own reason for
    leaving every row locked in the first place."""
    view = backtest_screen
    search_root = _open_order_execution_modal(qapp, qml_item, view)
    checkbox = qml_item(search_root, "triggerCheckBox_2")
    assert checkbox is not None

    view_model = view._view_model
    assert view_model.executionMode == "BAR_CLOSE"

    checkbox.setProperty("checked", True)
    qapp.processEvents()
    assert view_model.executionMode == "HISTORICAL_TICK"

    checkbox.setProperty("checked", False)
    qapp.processEvents()
    assert view_model.executionMode == "BAR_CLOSE"


def test_setting_execution_mode_from_python_updates_the_modal_checkboxes(
    qapp, qml_item, backtest_screen
):
    """The reverse direction: an external reset (e.g. FSM going back to IDLE)
    must not leave the modal showing a stale selection."""
    view = backtest_screen
    search_root = _open_order_execution_modal(qapp, qml_item, view)

    view._view_model.executionMode = "HISTORICAL_TICK"
    qapp.processEvents()

    bar_close_checkbox = qml_item(search_root, "triggerCheckBox_0")
    tick_checkbox = qml_item(search_root, "triggerCheckBox_2")
    assert bar_close_checkbox.property("checked") is False
    assert tick_checkbox.property("checked") is True
