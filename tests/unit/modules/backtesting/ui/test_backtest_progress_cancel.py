"""The Backtest run/sync progress, in the status bar (`EPIC-033L`).

It was a banner at the top of the results with its own Cancel button: a
second way to Tools → Stop backtest, which `test_backtest_commands.py`
proves applies while a run or its sync can stop. The status bar shows the
words and the bar; stopping is the command's.
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
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import (
    CANCELLING_CAPTION,
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
    presenter = BackTestPresenter(view, container)
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return view, presenter


def test_the_progress_shows_in_the_status_bar_only_while_a_run_or_sync_goes(
    qapp, backtest_screen
):
    view, presenter = backtest_screen
    view_model = presenter._view_model
    text, bar = view.status_widgets()
    assert text.isHidden() and bar.isHidden()

    for mode in ("SYNCING", "RUNNING", "CANCELLING"):
        view_model.set_ui_mode(mode)
        assert not text.isHidden(), mode
        assert not bar.isHidden(), mode

    view_model.set_ui_mode("IDLE")
    assert text.isHidden() and bar.isHidden()


def test_stopping_says_so_and_has_no_measure(qapp, backtest_screen):
    view, presenter = backtest_screen
    text, bar = view.status_widgets()

    presenter._view_model.set_ui_mode("CANCELLING")

    assert text.text() == CANCELLING_CAPTION
    assert bar.maximum() == 0  # Qt's busy indicator


def test_progress_status_text_and_percent_are_wired(qapp, backtest_screen):
    """Both progress sources (`syncProgressText`/`Percent` and
    `backtestProgressText`/`Percent`) reach the same two widgets; the mode
    picks the source."""
    view, presenter = backtest_screen
    text, bar = view.status_widgets()
    view_model = presenter._view_model

    view_model.run_progress.set_sync_progress(45.0, "Syncing candles: 45/100 (45%)")
    view_model.set_ui_mode("SYNCING")

    assert text.text() == "Syncing candles: 45/100 (45%)"
    assert bar.value() == 45

    view_model.set_ui_mode("IDLE")
    view_model.run_progress.set_backtest_progress(80.0, "Running full dataset: 80%")
    view_model.set_ui_mode("RUNNING")

    assert text.text() == "Running full dataset: 80%"
    assert bar.value() == 80


def test_progress_status_clamps_an_out_of_range_percent(qapp, backtest_screen):
    """`backtestProgressPercent`/`syncProgressPercent` are not clamped at the
    getter; the status clamps, so a future caller cannot show "150%"."""
    view, presenter = backtest_screen
    _text, bar = view.status_widgets()
    view_model = presenter._view_model

    view_model.run_progress.set_backtest_progress(150.0, "over")
    view_model.set_ui_mode("RUNNING")
    assert bar.value() == 100

    view_model.set_ui_mode("IDLE")
    view_model.run_progress.set_backtest_progress(-10.0, "under")
    view_model.set_ui_mode("RUNNING")
    assert bar.value() == 0
