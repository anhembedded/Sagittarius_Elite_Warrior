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


def test_progress_banner_cancel_button_in_running_and_syncing_modes(
    qapp, backtest_screen, qml_item
):
    """`ProgressBannerWidget` (QML, `EPIC-015` Phase 4) replaced
    `AppProgressBar` + a standalone Cancel `QPushButton` — the Cancel button
    now lives inside the QML scene (`kit/Button.qml`, `objectName:
    "progressBannerCancelButton"`), reached via `qml_item`
    (`tests/conftest.py`) rather than a direct widget attribute, same as
    every other `Repeater`/QML-scene lookup in this rollout."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    view, presenter = backtest_screen
    banner = view.top_widget._progress_banner
    progress_widget = view.top_widget._progress_banner_widget
    view_model = presenter._view_model

    def cancel_button():
        button = qml_item(progress_widget.root_object, "progressBannerCancelButton")
        assert button is not None
        return button

    def click(button):
        centre = button.mapToScene(button.boundingRect().center())
        QTest.mouseClick(
            progress_widget,
            Qt.MouseButton.LeftButton,
            pos=QPoint(int(centre.x()), int(centre.y())),
        )

    # 1. In IDLE mode, progress banner is hidden
    assert banner.isVisible() is False

    # 2. In SYNCING mode, banner and cancel button are visible and enabled
    view_model.set_ui_mode("SYNCING")
    qapp.processEvents()

    assert banner.isVisible() is True
    button = cancel_button()
    assert button.property("enabled") is True
    label = qml_item(button, "buttonLabel")
    assert label.property("text") == "Hủy"

    # Click Cancel on progress banner
    cancel_signal_called = False

    def on_cancel():
        nonlocal cancel_signal_called
        cancel_signal_called = True

    view_model.cancelBacktestRequested.connect(on_cancel)
    click(button)
    qapp.processEvents()

    assert cancel_signal_called is True

    # 3. In CANCELLING mode, button is disabled and text is "Đang hủy..."
    view_model.set_ui_mode("CANCELLING")
    qapp.processEvents()

    assert banner.isVisible() is True
    button = cancel_button()
    assert button.property("enabled") is False
    label = qml_item(button, "buttonLabel")
    assert label.property("text") == "Đang hủy..."

    # 4. In RUNNING mode, button is enabled and text is "Hủy"
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    assert banner.isVisible() is True
    button = cancel_button()
    assert button.property("enabled") is True
    label = qml_item(button, "buttonLabel")
    assert label.property("text") == "Hủy"


def test_progress_banner_status_text_and_percent_are_wired(
    qapp, backtest_screen, qml_item
):
    """Both progress sources (`syncProgressText`/`Percent` and
    `backtestProgressText`/`Percent`) reach `ProgressBannerWidget` through
    the same two setters — `_sync_banners()` picks the source, the widget
    itself is source-agnostic."""
    view, presenter = backtest_screen
    progress_widget = view.top_widget._progress_banner_widget
    view_model = presenter._view_model

    view_model.set_sync_progress(45.0, "Đang đồng bộ nến: 45/100 (45%)")
    view_model.set_ui_mode("SYNCING")
    qapp.processEvents()

    status = qml_item(progress_widget.root_object, "progressBannerStatusText")
    percent = qml_item(progress_widget.root_object, "progressBannerPercentText")
    assert status.property("text") == "Đang đồng bộ nến: 45/100 (45%)"
    assert percent.property("text") == "45%"

    view_model.set_ui_mode("IDLE")
    view_model.set_backtest_progress(80.0, "Chạy toàn bộ dữ liệu: 80%")
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    status = qml_item(progress_widget.root_object, "progressBannerStatusText")
    percent = qml_item(progress_widget.root_object, "progressBannerPercentText")
    assert status.property("text") == "Chạy toàn bộ dữ liệu: 80%"
    assert percent.property("text") == "80%"


def test_progress_banner_clamps_an_out_of_range_percent(
    qapp, backtest_screen, qml_item
):
    """`BackTestViewModel.backtestProgressPercent`/`syncProgressPercent` are
    not clamped at the property getter the way
    `DataManagementViewModel.progressPercent` is — every real call site
    clamps before storing, but `_sync_banners()` still defends against a
    value that is not, so a future caller cannot silently show "150%"."""
    view, presenter = backtest_screen
    progress_widget = view.top_widget._progress_banner_widget
    view_model = presenter._view_model

    view_model.set_backtest_progress(150.0, "over")
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    percent = qml_item(progress_widget.root_object, "progressBannerPercentText")
    assert percent.property("text") == "100%"

    view_model.set_ui_mode("IDLE")
    view_model.set_backtest_progress(-10.0, "under")
    view_model.set_ui_mode("RUNNING")
    qapp.processEvents()

    percent = qml_item(progress_widget.root_object, "progressBannerPercentText")
    assert percent.property("text") == "0%"
