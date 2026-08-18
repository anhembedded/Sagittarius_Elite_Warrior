"""BOT-098F6C sanity: NativeBacktestChart.qml itself — axes/tooltip/FPS
elements exist with the right object names and no QML warnings are
produced during construction or a real submission. Mirrors the
`booted_app` fixture from test_backtest_screen_ui_sanity.py /
test_native_backtest_chart_host_sanity.py so the real theme/import
bootstrap is exercised, not a dev-only shortcut.
"""

import os

import pytest
from PySide6.QtCore import QtMsgType, qInstallMessageHandler
from PySide6.QtQuick import QQuickItem

from Sagittarius_Elite_Warrior.src.main import create_app
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.native_backtest_chart_adapter import (
    NativeBacktestChartHost,
)
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

_CANDLES = [
    (1_700_000_000.0 + i * 60.0, 10.0 + i, 11.0 + i, 9.0 + i, 10.5 + i)
    for i in range(5)
]
_VOLUMES = [(t, 100.0, True) for t, *_ in _CANDLES]


@pytest.fixture
def booted_app():
    from unittest.mock import patch

    config_manager = ConfigManager()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_manager.load_json(os.path.join(base_dir, "src", "config", "app_config.json"))
    config_manager.load_json(
        os.path.join(base_dir, "src", "config", "user_config.json")
    )
    app = create_app(config_manager)
    with (
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.AsyncClient"
        ),
        patch(
            "Sagittarius_Elite_Warrior.src.infrastructure.binance.binance_websocket_service.BinanceSocketManager"
        ),
    ):
        app.boot()
        yield app
        app.stop()


def _find(root_item, object_name: str):
    return root_item.findChild(QQuickItem, object_name)


def test_wrapper_exposes_interaction_axis_tooltip_and_fps_elements(
    qapp, booted_app, request
):
    host = NativeBacktestChartHost.create()
    request.addfinalizer(host.widget.deleteLater)

    root_item = host._root_item
    assert _find(root_item, "interactionArea") is not None
    assert _find(root_item, "crosshairTooltip") is not None
    assert _find(root_item, "devFpsOverlay") is not None


def test_construction_and_submission_produce_no_qml_warnings(qapp, booted_app, request):
    messages: list[str] = []

    def capture(message_type, _context, message: str) -> None:
        if message_type in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg):
            messages.append(message)

    previous_handler = qInstallMessageHandler(capture)
    try:
        host = NativeBacktestChartHost.create()
        request.addfinalizer(host.widget.deleteLater)
        assert host.submit_ohlcv(_CANDLES, _VOLUMES, action_id=1, generation=0) is True
        host.set_dev_fps_enabled(True)
        host.set_display_timezone("Asia/Ho_Chi_Minh")
        qapp.processEvents()
    finally:
        qInstallMessageHandler(previous_handler)

    assert messages == []


def test_initial_viewport_shows_the_latest_150_candles_or_fewer(
    qapp, booted_app, request
):
    host = NativeBacktestChartHost.create()
    request.addfinalizer(host.widget.deleteLater)

    assert host.submit_ohlcv(_CANDLES, _VOLUMES, action_id=1, generation=0) is True
    qapp.processEvents()

    assert host._chart_item.property("viewportStart") == 0.0
    assert host._chart_item.property("viewportEnd") == float(len(_CANDLES))


def test_price_and_time_axis_tick_repeaters_populate_after_a_real_snapshot(
    qapp, booted_app, request
):
    host = NativeBacktestChartHost.create()
    request.addfinalizer(host.widget.deleteLater)

    assert host.submit_ohlcv(_CANDLES, _VOLUMES, action_id=1, generation=0) is True
    qapp.processEvents()

    price_ticks = host._chart_item.property("priceAxisTicks")
    time_ticks = host._chart_item.property("timeAxisTicks")
    assert len(price_ticks) > 0
    assert len(time_ticks) > 0
    assert "value" in price_ticks[0]
    assert "timestampUtcMs" in time_ticks[0]
