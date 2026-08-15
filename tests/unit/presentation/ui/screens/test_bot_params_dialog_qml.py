"""
Regression test (BOT-047 follow-up): user reported two console warnings from
BotParamField.qml ("Unable to assign [undefined] to QString/QColor") when the
Backtest screen loads. Root-cause investigation raised the possibility that
the dynamic form inside the "Thông số Bot" Popup never actually renders any
field — this test opens the real dialog through the real QML tree and
asserts a real field widget exists and is usable, per the project rule
(`.agents/rules/code-rule.md`): reproduce with a test before fixing.

Popup content is reparented to the window's Overlay for rendering, so it is
NOT reachable from `rootObject()` via `qml_item`/`walk_qml_items` (which
walks the *root's own* visual child tree) — this searches from the window's
own content item instead, which IS an ancestor of the Overlay.
"""

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


def _open_bot_params_dialog(presenter, qapp, qml_item):
    root = presenter.view.top_widget.rootObject()
    btn = qml_item(root, "btnBacktestBotParams")
    btn.clicked.emit()
    qapp.processEvents()
    qapp.processEvents()
    return presenter.view.top_widget.quickWindow().contentItem()


def test_opening_bot_params_dialog_renders_a_real_field_widget(
    qapp, qml_item, bot_params_presenter
):
    """The declared `period` parameter must produce a usable, visible
    TextField in the dialog — not silently render nothing."""
    window_content = _open_bot_params_dialog(bot_params_presenter, qapp, qml_item)

    field = qml_item(window_content, "fldBotParam_period")

    assert field is not None
    assert field.property("text") == "20"


def test_editing_and_saving_bot_params_sends_the_typed_value(
    qapp, qml_item, bot_params_presenter
):
    """End-to-end: type into the real field, click "Lưu & Re-Backtest", and
    confirm the ViewModel's save signal carries the typed value keyed by
    the right param name — not an empty/garbage dict (see
    BotParamsDialog.saveAndRerun(), which keys the values dict by each
    field's `fieldName`)."""
    window_content = _open_bot_params_dialog(bot_params_presenter, qapp, qml_item)

    field = qml_item(window_content, "fldBotParam_period")
    assert field is not None
    field.setProperty("text", "42")
    field.editingFinished.emit()
    qapp.processEvents()

    save_btn = qml_item(window_content, "btnBotParamsSave")
    assert save_btn is not None

    received = {}

    def _on_save_requested(values):
        received.update(values)

    bot_params_presenter._view_model.botParamsSaveRequested.connect(_on_save_requested)
    save_btn.clicked.emit()
    qapp.processEvents()

    assert received == {"period": "42"}
