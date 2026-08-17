"""
Unit test for OrderExecutionModal (BOT-074).
Asserts that all execution trigger rules are truthfully displayed with proper lock states:
- 'On bar close' is active (checked=True) and locked (enabled=False, cannot be toggled off in current engine).
- Unimplemented modes are inactive (checked=False) and locked (enabled=False, pending Epic BOT-073 / BOT-076).

NOTE for future developers:
When BOT-076 / BOT-077 implements tick-level / order-fill execution modes and connects them
to Python ViewModel, this test will fail by design to ensure the new capability is intentionally
unlocked and verified with real Python plumbing.
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


def test_order_execution_modal_all_items_locked_truthfully(
    qapp, qml_item, backtest_screen
):
    """
    Asserts BOT-074:
    - All 4 triggers must have enabled == False (locked).
    - Trigger 0 ('On bar close') must be checked == True.
    - Triggers 1, 2, 3 must be checked == False.
    """
    view = backtest_screen
    top_root = view.top_widget.rootObject()
    overlay_host = view.overlay_host

    # Open Order Execution Modal
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
    search_root = modal.property("contentItem") or modal

    # Search visual children of modal contentItem
    for i in range(4):
        item = qml_item(search_root, f"chkExecutionTrigger_{i}")
        assert item is not None, (
            f"chkExecutionTrigger_{i} not found in OrderExecutionModal"
        )

        checkbox = qml_item(search_root, f"triggerCheckBox_{i}")
        assert checkbox is not None, (
            f"triggerCheckBox_{i} not found in OrderExecutionModal"
        )
        checked_val = checkbox.property("checked")

        if i == 0:
            assert checked_val is True, (
                f"Trigger 0 ('On bar close') should be checked, but was {checked_val}"
            )
        else:
            assert checked_val is False, (
                f"Trigger {i} should not be checked, but was {checked_val}"
            )

        # Must be locked / disabled: enabled should be False
        assert item.property("enabled") is False, (
            f"Trigger item {i} should be disabled/locked (enabled=False), but was enabled={item.property('enabled')}"
        )
        assert checkbox.property("enabled") is False, (
            f"Trigger checkbox {i} should be disabled/locked (enabled=False), but was enabled={checkbox.property('enabled')}"
        )
