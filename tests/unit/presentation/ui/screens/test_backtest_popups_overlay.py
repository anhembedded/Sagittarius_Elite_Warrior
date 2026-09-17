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
from PySide6.QtWidgets import QLabel
from Sagittarius_Elite_Warrior.src.modules.strategy.application.services.strategy_registry import (
    StrategyRegistry,
)
from Sagittarius_Elite_Warrior.src.modules.strategy.domain.strategies.base_strategy import (
    BaseStrategy,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_presenter import (
    BackTestPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view import (
    BackTestView,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.backtest_chart_host import (
    BacktestChartHostFactory,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.extended_metrics_snapshot import (
    ExtendedMetricsSnapshot,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.performance_metrics_view import (
    StatCardData,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import SelectableCard, Tone


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
    _neutral = Tone.NEUTRAL
    presenter._view_model.run_result.set_extended_metrics_snapshot(
        ExtendedMetricsSnapshot(
            cards=(
                StatCardData("Gross Profit", "100.00", _neutral, "USD", "", _neutral),
                StatCardData("Gross Loss", "-50.00", _neutral, "USD", "", _neutral),
            ),
            gross_profit=100.0,
            gross_loss=-50.0,
            profit_factor=2.0,
            total_closed_trades=10,
            fee_rate_percent=0.1,
        )
    )
    qapp.processEvents()

    presenter._view_model.requestOpenExtendedMetrics()
    qapp.processEvents()

    dialog = view._modals_host._extended_metrics
    assert dialog is not None
    assert dialog.objectName() == "backtestMetricsDetailDialog"
    assert dialog.isVisible() is True
    # `EPIC-025` PR 4.3j: a `QTreeWidget` with one top-level item per section,
    # so the assertion is on what is actually on screen rather than on a
    # ViewModel's `QVariantList` — which is what the QML version left it as,
    # its delegates carrying no per-row objectName to find.
    section = next(
        dialog._tree.topLevelItem(index)
        for index in range(dialog._tree.topLevelItemCount())
        if dialog._tree.topLevelItem(index).text(0) == "PROFIT & LOSS"
    )
    assert {section.child(index).text(0) for index in range(section.childCount())} == {
        "GROSS PROFIT",
        "GROSS LOSS",
    }


def test_limitations_popup_opens_with_each_limitation_as_its_own_label(
    qapp, backtest_screen
):
    view, presenter = backtest_screen
    presenter._view_model.run_result.set_limitations(["Limitation 1", "Limitation 2"])
    qapp.processEvents()

    view.top_widget._btn_limitations.click()
    qapp.processEvents()

    dialog = view._modals_host._limitations
    assert dialog is not None
    assert dialog.objectName() == "limitationsPopup"
    assert dialog.isVisible() is True
    # `EPIC-025` PR 4.3e: one wrapped `QLabel` per caveat. `EPIC-015` §4c had
    # served this from `SelectList.qml` with `selectable=False`, which is a
    # picker with its only promise switched off — see `EPIC-025E` §4.5.
    rows = [
        label
        for label in dialog.findChildren(QLabel)
        if label.objectName().startswith("lblLimitation_")
    ]
    assert [label.text() for label in rows] == ["• Limitation 1", "• Limitation 2"]


def test_capital_popup_opens_with_the_capital_field_populated(qapp, backtest_screen):
    view, _ = backtest_screen

    view.top_widget._btn_capital.click()
    qapp.processEvents()

    dialog = view._modals_host._capital
    assert dialog is not None
    assert dialog.objectName() == "capitalDialog"
    assert dialog.isVisible() is True
    # `EPIC-025` PR 4.3f: a `QLineEdit` again, and the objectName is
    # deliberately unchanged across all three versions of this dialog.
    assert dialog._field.objectName() == "txtBacktestCapital"
    assert dialog._field.text() != ""


def test_capital_dialog_apply_button_disables_on_invalid_capital(qapp, backtest_screen):
    """Regression: `CapitalDialogWidget.__init__` used to overwrite the real
    Apply button `_build_buttons()` had already created (called by `Overlay.
    __init__` before this class's own `__init__` body runs any further) with
    a bare `self._btn_apply = None` at the end of `__init__` — so `_sync_
    validation()`'s guard was always False and the button could never be
    disabled, letting a user submit an invalid capital value.

    `EPIC-015` bậc 1 moved the body to QML and `EPIC-025` PR 4.3f moved it
    back, and through all three the Apply button stayed `Overlay` chrome built
    by that hook — so the same overwrite is still possible and this test still
    guards it. It now drives the **real** presenter: clearing the field emits
    `textEdited`, which asks for validation, whose verdict is the only thing
    that disables the button."""
    view, _ = backtest_screen

    view.top_widget._btn_capital.click()
    qapp.processEvents()

    dialog = view._modals_host._capital
    assert dialog._btn_apply.isEnabled() is True

    dialog._field.clear()
    dialog._field.textEdited.emit("")
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
    # `EPIC-025` PR 4.3e: the shared `kit.PickerOverlay`, one `SelectableCard`
    # per registered strategy.
    cards = [
        entry.widget()
        for entry in (dialog._grid.itemAt(i) for i in range(dialog._grid.count()))
        if entry is not None and isinstance(entry.widget(), SelectableCard)
    ]
    assert len(cards) == 1


def test_timeframe_picker_modal_opens_and_lists_every_timeframe_option(
    qapp, backtest_screen
):
    """`EPIC-015` bậc 1: body is now the standalone `TimeframePicker.qml` —
    its own grouped grid, not the QtWidgets `TimeframeCard` list this
    replaces."""
    view, presenter = backtest_screen

    view.top_widget._btn_timeframe.click()
    qapp.processEvents()

    dialog = view._modals_host._timeframe_picker
    assert dialog is not None
    assert dialog.objectName() == "timeframePickerDialog"
    assert dialog.isVisible() is True
    # `EPIC-025` PR 4.3k: a `QTreeWidget` of groups, so the count is the rows
    # under the headings rather than delegates in a Quick scene.
    rows = [
        dialog._tree.topLevelItem(group).child(child)
        for group in range(dialog._tree.topLevelItemCount())
        for child in range(dialog._tree.topLevelItem(group).childCount())
    ]
    assert len(rows) == len(presenter._view_model.timeframeOptions)
    # EPIC-014: the picker used to offer `DEFAULT_TIMEFRAMES` (5 of the
    # domain's 16). Asserting the real number here, not just "same as the
    # ViewModel", so a regression back to the toolbar tuple is a failure.
    assert len(rows) == 16


def test_time_range_picker_modal_opens_and_lists_every_preset(qapp, backtest_screen):
    """`EPIC-015` put the standalone `TimeRangePicker.qml` here; `EPIC-025` PR
    4.3d replaced it with `support/ui_kit/time_range_picker`'s `QDialog`, and
    the count this test holds survived the swap unchanged.

    Both offer a "Today" preset the screen's own
    `BackTestViewModel.time_range.presetOptions` does not — an accepted gain,
    so this is deliberately **one more** than the ViewModel's option list
    rather than the same number. Asserting the real count too, so a regression
    to the six-row list is a failure rather than a coincidence."""
    view, presenter = backtest_screen

    view.top_widget._btn_range.click()
    qapp.processEvents()

    dialog = view._modals_host._time_range_picker
    assert dialog is not None
    assert dialog.objectName() == "backtestTimeRangePickerDialog"
    assert dialog.isVisible() is True
    assert len(dialog._preset_buttons) == (
        len(presenter._view_model.time_range.presetOptions) + 1
    )
    assert len(dialog._preset_buttons) == 7
