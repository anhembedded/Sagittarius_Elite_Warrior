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
from PySide6.QtCore import QObject
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
from Sagittarius_Elite_Warrior.tests.unit.presentation.ui.qml._qml_test_support import (
    named_descendants,
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
    # EPIC-015 §4c: body is StatGrid.qml now; each card is a delegate the
    # Repeater creates, only reachable through childItems() (see
    # `_qml_test_support`'s module docstring).
    cards = [
        item
        for item in named_descendants(dialog.root_object)
        if item.objectName().startswith("statCard_")
    ]
    assert len(cards) == 2


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
    # EPIC-015 §4c: body is SelectList.qml with selectable=False, so each
    # limitation is a "bulletItem_" delegate rather than a QLabel.
    rows = [
        item
        for item in named_descendants(dialog.root_object)
        if item.objectName().startswith("bulletItem_")
    ]
    assert len(rows) == 2


def test_capital_popup_opens_with_the_capital_field_populated(qapp, backtest_screen):
    view, _ = backtest_screen

    view.top_widget._btn_capital.click()
    qapp.processEvents()

    dialog = view._modals_host._capital
    assert dialog is not None
    assert dialog.objectName() == "capitalDialog"
    assert dialog.isVisible() is True
    # EPIC-015 bậc 1: the body is Capital.qml now, so the amount is read off
    # the QML TextField instead of a QLineEdit attribute. The objectName is
    # deliberately unchanged, so this still names the same field.
    field = dialog.root_object.findChild(QObject, "txtBacktestCapital")
    assert field is not None
    assert field.property("text") != ""


def test_capital_dialog_apply_button_disables_on_invalid_capital(qapp, backtest_screen):
    """Regression: `CapitalDialogWidget.__init__` used to overwrite the real
    Apply button `_build_buttons()` had already created (called by `Overlay.
    __init__` before this class's own `__init__` body runs any further) with
    a bare `self._btn_apply = None` at the end of `__init__` — so `_sync_
    validation()`'s guard was always False and the button could never be
    disabled, letting a user submit an invalid capital value.

    `EPIC-015` bậc 1 moved the body to QML but kept the Apply button in
    `Overlay`'s chrome, so the same overwrite is still possible and this test
    still guards it. Only how the amount is typed changed: assigning
    `_widget_vm.text` is exactly what the QML `onTextEdited` handler does."""
    view, _ = backtest_screen

    view.top_widget._btn_capital.click()
    qapp.processEvents()

    dialog = view._modals_host._capital
    assert dialog._btn_apply.isEnabled() is True

    dialog._widget_vm.text = ""
    qapp.processEvents()

    assert dialog._btn_apply.isEnabled() is False


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
    # EPIC-015 §4c: body is the shared SelectList.qml, selectable=True.
    rows = [
        item
        for item in named_descendants(dialog.root_object)
        if item.objectName().startswith("selectItem_")
    ]
    assert len(rows) == 1


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
    assert len(dialog._cards) == len(presenter._view_model.timeframeOptions)
    # EPIC-014: the picker used to offer `DEFAULT_TIMEFRAMES` (5 of the
    # domain's 16). Asserting the real number here, not just "same as the
    # ViewModel", so a regression back to the toolbar tuple is a failure.
    assert len(dialog._cards) == 16


def test_time_range_picker_modal_opens_and_lists_every_preset(qapp, backtest_screen):
    """`EPIC-015`: body is now the standalone `TimeRangePicker.qml` — its
    preset list is `TimeRangePickerVM`'s own hardcoded set (confirmed
    label-compatible with `BackTestViewModel.timeRangePresetOptions`, see
    `qml/TimeRangePicker/time_range_picker_vm.py`), plus a bonus "Hôm nay"
    entry that dialog never offered — one more row than the ViewModel's own
    option list, not the same count."""
    view, presenter = backtest_screen

    view.top_widget._btn_range.click()
    qapp.processEvents()

    dialog = view._modals_host._time_range_picker
    assert dialog is not None
    assert dialog.objectName() == "backtestTimeRangePickerDialog"
    assert dialog.isVisible() is True
    rows = [
        item
        for item in named_descendants(dialog.root_object)
        if item.objectName().startswith("timeRangePreset_")
    ]
    assert len(rows) == len(presenter._view_model.timeRangePresetOptions) + 1
