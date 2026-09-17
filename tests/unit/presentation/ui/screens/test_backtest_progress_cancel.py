"""The Backtest run/sync progress banner and its Cancel button.

Was `test_backtest_progress_cancel_qml.py` until `EPIC-025` PR 4.3l: the
Cancel button lived inside `ProgressBanner.qml` and had to be reached through
`qml_item(widget.root_object, ...)` and clicked at scene coordinates. It is a
`QPushButton` inside `kit.ProgressBanner` now (ADR D21), so the same three
promises are asserted against widgets — and the click is
`QPushButton.click()`, which is what a test of a *wiring* should use anyway:
the scene-coordinate `QTest.mouseClick` passed whether or not the banner was
laid out where it was aimed.
"""

from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
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


def _cancel_button(banner):
    """The `QPushButton` inside the banner, by `objectName` rather than by
    the private attribute, so this test sees what a screenshot would."""
    from PySide6.QtWidgets import QPushButton

    button = banner.findChild(QPushButton, "progressBannerCancel")
    assert button is not None
    return button


def test_progress_banner_cancel_button_in_running_and_syncing_modes(
    qapp, backtest_screen
):
    """`CANCELLING` disables the button; `kit.ProgressBanner` deliberately
    does not relabel it, so the word the user reads is the panel's own
    (`_sync_banners()` puts "Cancelling safely..." in the caption instead of
    on the button, which is what it already did through the `.qml`)."""
    view, presenter = backtest_screen
    banner = view.top_widget._progress_banner
    widget = view.top_widget._progress_banner_widget
    view_model = presenter._view_model

    # 1. In IDLE mode, progress banner is hidden
    assert banner.isVisible() is False

    # 2. In SYNCING mode, banner and cancel button are visible and enabled
    view_model.set_ui_mode("SYNCING")
    qapp.processEvents()

    assert banner.isVisible() is True
    button = _cancel_button(widget)
    assert button.isEnabled() is True
    assert button.text() == "Cancel"

    # Click Cancel on progress banner
    cancel_signal_called = False

    def on_cancel():
        nonlocal cancel_signal_called
        cancel_signal_called = True

    view_model.cancelBacktestRequested.connect(on_cancel)
    button.click()
    qapp.processEvents()

    assert cancel_signal_called is True

    # 3. In CANCELLING mode the button is disabled, and the caption — not the
    #    button — carries the word.
    view_model.set_ui_mode("CANCELLING")
    qapp.processEvents()

    assert banner.isVisible() is True
    assert _cancel_button(widget).isEnabled() is False
    assert widget._status.text() == CANCELLING_CAPTION

    # 4. In RUNNING mode, button is enabled and text is "Cancel"
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert banner.isVisible() is True
    button = _cancel_button(widget)
    assert button.isEnabled() is True
    assert button.text() == "Cancel"


def test_progress_banner_status_text_and_percent_are_wired(qapp, backtest_screen):
    """Both progress sources (`syncProgressText`/`Percent` and
    `backtestProgressText`/`Percent`) reach the banner through the same two
    setters — `_sync_banners()` picks the source, the widget itself is
    source-agnostic."""
    view, presenter = backtest_screen
    widget = view.top_widget._progress_banner_widget
    view_model = presenter._view_model

    view_model.run_progress.set_sync_progress(45.0, "Syncing candles: 45/100 (45%)")
    view_model.set_ui_mode("SYNCING")
    qapp.processEvents()

    assert widget._status.text() == "Syncing candles: 45/100 (45%)"
    assert widget._bar.text() == "45%"

    view_model.set_ui_mode("IDLE")
    view_model.run_progress.set_backtest_progress(80.0, "Running full dataset: 80%")
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert widget._status.text() == "Running full dataset: 80%"
    assert widget._bar.text() == "80%"


def test_progress_banner_clamps_an_out_of_range_percent(qapp, backtest_screen):
    """`BackTestViewModel.backtestProgressPercent`/`syncProgressPercent` are
    not clamped at the property getter the way
    `DataManagementViewModel.progressPercent` is — every real call site
    clamps before storing, but `_sync_banners()` still defends against a
    value that is not, so a future caller cannot silently show "150%"."""
    view, presenter = backtest_screen
    widget = view.top_widget._progress_banner_widget
    view_model = presenter._view_model

    view_model.run_progress.set_backtest_progress(150.0, "over")
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert widget._bar.text() == "100%"

    view_model.set_ui_mode("IDLE")
    view_model.run_progress.set_backtest_progress(-10.0, "under")
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert widget._bar.text() == "0%"
