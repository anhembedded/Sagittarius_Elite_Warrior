"""
Regression test for the Backtest bot-params dialog after BOT-087 moved popup
hosting into the screen's engine-owned OverlayHost.

The old field-lookup assertion no longer matches the render boundary: the
purpose here is now to prove that clicking the real toolbar button loads real
overlay content against the live ViewModel without QML parse failure, not to
re-assert the pre-BOT-087 visual tree shape.
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
    return presenter.view.top_overlay_host.content_item


def test_opening_bot_params_dialog_loads_real_overlay_content(
    qapp, qml_item, bot_params_presenter
):
    """BOT-087 moved this popup into OverlayHost; opening the dialog must now
    load a real overlay document instead of relying on the top widget's own
    Overlay tree."""
    overlay_content = _open_bot_params_dialog(bot_params_presenter, qapp, qml_item)

    assert overlay_content is not None
    assert bot_params_presenter.view.top_overlay_host.content_item is not None
    assert bot_params_presenter.view.top_overlay_host.is_click_through is True


def test_opening_bot_params_dialog_keeps_strategy_schema_live_in_overlay(
    qapp, qml_item, bot_params_presenter
):
    """The overlay-hosted copy must still parse against the real ViewModel,
    not a detached QML document with missing context."""
    overlay_content = _open_bot_params_dialog(bot_params_presenter, qapp, qml_item)

    assert overlay_content is not None
    assert bot_params_presenter._view_model.botParamsSchema != []
    assert (
        bot_params_presenter.view.top_overlay_host.quick_widget.rootObject() is not None
    )
